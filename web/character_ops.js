import { app } from "../../scripts/app.js";
import { api } from "../../scripts/api.js";

function widget(node, name) {
  return node.widgets?.find((item) => item.name === name);
}

function setStatus(node, value) {
  const status = widget(node, "运行状态");
  if (status) status.value = value;
  node.setDirtyCanvas?.(true, true);
}

function workflowMode(node) {
  const locked = String(node.properties?.locked_mode || "").toLowerCase();
  if (locked === "anima" || locked === "krea2") return locked;
  return String(widget(node, "mode")?.value || "anima").toLowerCase();
}

function applyModeLock(node) {
  const locked = String(node.properties?.locked_mode || "").toLowerCase();
  if (locked !== "anima" && locked !== "krea2") return;
  const modeWidget = widget(node, "mode");
  if (!modeWidget) return;
  modeWidget.value = locked;
  modeWidget.options ||= {};
  modeWidget.options.values = [locked];
  modeWidget.label =
    locked === "anima"
      ? "提示词库：Anima Tag 串（工作流自动）"
      : "提示词库：Krea2 自然语言（工作流自动）";
  node.setDirtyCanvas?.(true, true);
}

function showProfile(node, mode) {
  const selected = node.properties?.profile?.[mode];
  if (!selected) return;
  const stable = widget(node, "stable_prefix");
  const cover = widget(node, "cover_prompt");
  if (stable) stable.value = selected.stable_prefix || "";
  if (cover) cover.value = selected.cover_prompt || "";
  node.setDirtyCanvas?.(true, true);
}

async function parseResponse(response) {
  const text = await response.text();
  let payload = {};
  try {
    payload = text ? JSON.parse(text) : {};
  } catch {
    payload = { error: text || `HTTP ${response.status}` };
  }
  if (!response.ok) throw new Error(payload.error || `HTTP ${response.status}`);
  return payload;
}

function selectFile(accept) {
  return new Promise((resolve) => {
    const input = document.createElement("input");
    input.type = "file";
    input.accept = accept;
    input.style.display = "none";
    const finish = (value) => {
      input.remove();
      resolve(value);
    };
    input.addEventListener("change", () => finish(input.files?.[0] || null), {
      once: true,
    });
    input.addEventListener("cancel", () => finish(null), { once: true });
    document.body.appendChild(input);
    input.click();
  });
}

async function uploadFile(file, endpoint) {
  const form = new FormData();
  form.append("file", file);
  return parseResponse(await fetch(endpoint, { method: "POST", body: form }));
}

function addActionButton(node, label, callback) {
  const action = node.addWidget("button", label, null, callback);
  action.serialize = false;
  action.serializeValue = () => undefined;
  return action;
}

async function queueBatch(node, coverCount, galleryCount) {
  const cardRef = node.properties.card_ref || "";
  const poolRef = node.properties.pool_ref || "";
  if (!cardRef) {
    setStatus(node, "请先上传角色卡并等待人物提示词提取完成。");
    return;
  }
  if (galleryCount > 0 && !poolRef) {
    setStatus(node, "生成后续图前请先上传 Excel 提示词池。");
    return;
  }

  const mode = workflowMode(node);
  const stablePrefix = String(widget(node, "stable_prefix")?.value || "").trim();
  const coverPrompt = String(widget(node, "cover_prompt")?.value || "").trim();
  if (coverCount > 0 && !coverPrompt) {
    setStatus(node, "封面人物提示词为空，请重新上传角色卡。");
    return;
  }
  if (galleryCount > 0 && !stablePrefix) {
    setStatus(node, "稳定人物提示词为空，请重新上传角色卡。");
    return;
  }

  setStatus(node, `正在准备入队：封面 ${coverCount} / 后续 ${galleryCount}…`);
  try {
    const promptData = await app.graphToPrompt();
    const result = await parseResponse(
      await fetch("/character_ops/start_batch", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          card_ref: cardRef,
          pool_ref: poolRef,
          mode,
          cover_count: coverCount,
          gallery_count: galleryCount,
          stable_prefix_override: stablePrefix,
          cover_prompt_override: coverPrompt,
          prompt: promptData.output,
          workflow: promptData.workflow,
          client_id: api.clientId,
        }),
      }),
    );
    setStatus(
      node,
      `${result.character_name}：已入队 ${result.queued} 张（封面 ${result.cover_count} / 后续 ${result.gallery_count}）`,
    );
  } catch (error) {
    setStatus(node, `批量入队失败：${error.message}`);
  }
}

app.registerExtension({
  name: "codex.character.ops.canvas-controller",

  async beforeRegisterNodeDef(nodeType, nodeData) {
    if (nodeData.name !== "CharacterOpsBatchController") return;

    const originalOnConfigure = nodeType.prototype.onConfigure;
    nodeType.prototype.onConfigure = function onConfigure() {
      originalOnConfigure?.apply(this, arguments);
      applyModeLock(this);
    };

    const originalOnNodeCreated = nodeType.prototype.onNodeCreated;
    nodeType.prototype.onNodeCreated = function onNodeCreated() {
      originalOnNodeCreated?.apply(this, arguments);
      this.properties ||= {};
      this.properties.card_ref = "";
      this.properties.pool_ref = "";
      this.properties.card_name = "";
      this.properties.pool_name = "";
      this.properties.profile = null;
      this.title = "角色图两阶段自动化 · 可拖动";
      this.size = [560, 720];

      const modeWidget = widget(this, "mode");
      const originalModeCallback = modeWidget?.callback;
      if (modeWidget) {
        modeWidget.callback = (value, ...args) => {
          const selectedMode = workflowMode(this);
          modeWidget.value = selectedMode;
          originalModeCallback?.call(modeWidget, selectedMode, ...args);
          showProfile(this, selectedMode);
        };
      }
      const stableWidget = widget(this, "stable_prefix");
      const coverWidget = widget(this, "cover_prompt");
      if (stableWidget) stableWidget.label = "后续50张：稳定人物提示词（可编辑）";
      if (coverWidget) coverWidget.label = "封面2张：原文人物提示词（可编辑）";

      addActionButton(this, "① 上传角色卡并提取人物提示词", async () => {
        const file = await selectFile(".png,.json,image/png,application/json");
        if (!file) return;
        setStatus(this, "正在上传、解析角色卡并调用 LLM 提取提示词…");
        try {
          const result = await uploadFile(file, "/character_ops/upload_card");
          this.properties.card_ref = result.ref;
          this.properties.card_name = result.character_name || file.name;
          this.properties.profile = result.profile || null;
          showProfile(this, workflowMode(this));
          setStatus(this, `角色提示词已提取：${this.properties.card_name}`);
        } catch (error) {
          this.properties.card_ref = "";
          this.properties.profile = null;
          setStatus(this, `角色卡或提示词提取失败：${error.message}`);
        }
      });

      addActionButton(this, "② 先生成封面（按 cover_count）", async () => {
        const count = Math.max(0, Number(widget(this, "cover_count")?.value ?? 2));
        await queueBatch(this, count, 0);
      });

      addActionButton(this, "③ 上传后续图提示词池 XLSX", async () => {
        const file = await selectFile(
          ".xlsx,application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        );
        if (!file) return;
        setStatus(this, "正在上传并读取 Excel 提示词池…");
        try {
          const mode = workflowMode(this);
          const result = await uploadFile(
            file,
            `/character_ops/upload_pool?mode=${encodeURIComponent(mode)}`,
          );
          this.properties.pool_ref = result.ref;
          this.properties.pool_name = file.name;
          const count = Number(result[`${mode}_count`] || 0);
          const source = result.sources?.[mode];
          const modeLabel = mode === "anima" ? "Anima Tag 串" : "Krea2 自然语言";
          const sourceLabel = source ? `（${source.sheet} / ${source.column}）` : "";
          setStatus(
            this,
            `提示词池就绪：${modeLabel} ${count} 条${sourceLabel}`,
          );
        } catch (error) {
          this.properties.pool_ref = "";
          setStatus(this, `提示词池失败：${error.message}`);
        }
      });

      addActionButton(this, "④ 封面确认后生成后续图（按 gallery_count）", async () => {
        const count = Math.max(0, Number(widget(this, "gallery_count")?.value ?? 50));
        await queueBatch(this, 0, count);
      });

      const status = this.addWidget(
        "text",
        "运行状态",
        "第一步：上传角色卡并提取提示词",
        () => {},
        { multiline: true },
      );
      status.serialize = false;
      status.serializeValue = () => undefined;
      this.setSize?.([560, 720]);
    };
  },
});

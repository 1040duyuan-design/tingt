(function () {
  const form = document.getElementById("chat-form");
  const input = document.getElementById("message-input");
  const chatLog = document.getElementById("chat-log");
  const button = form.querySelector("button");
  const sessionId = crypto.randomUUID();
  const NETWORK_FALLBACK = "刚刚网络抖了一下，你再发一句。";
  const conversationHistory = [];

  function appendMessage(role, meta, text) {
    const wrapper = document.createElement("div");
    wrapper.className = `message ${role}`;

    const metaEl = document.createElement("p");
    metaEl.className = "meta";
    metaEl.textContent = meta;

    const textEl = document.createElement("p");
    textEl.textContent = text;

    wrapper.appendChild(metaEl);
    wrapper.appendChild(textEl);
    chatLog.appendChild(wrapper);
    chatLog.scrollTop = chatLog.scrollHeight;
  }

  function pushHistory(role, content) {
    conversationHistory.push({ role, content });
    if (conversationHistory.length > 12) {
      conversationHistory.splice(0, conversationHistory.length - 12);
    }
  }

  function appendPendingIndicator() {
    const wrapper = document.createElement("div");
    wrapper.className = "message assistant pending";

    const metaEl = document.createElement("p");
    metaEl.className = "meta";
    metaEl.textContent = "TingT 正在输入中";

    const textEl = document.createElement("p");
    textEl.className = "typing";
    textEl.setAttribute("aria-live", "polite");
    textEl.innerHTML = '<span></span><span></span><span></span>';

    wrapper.appendChild(metaEl);
    wrapper.appendChild(textEl);
    chatLog.appendChild(wrapper);
    chatLog.scrollTop = chatLog.scrollHeight;
    return wrapper;
  }

  function autosize() {
    input.style.height = "auto";
    input.style.height = `${Math.min(input.scrollHeight, 180)}px`;
  }

  async function onSubmit(event) {
    event.preventDefault();
    const message = input.value.trim();
    if (!message) return;

    appendMessage("user", "你", message);
    pushHistory("user", message);
    input.value = "";
    autosize();
    button.disabled = true;
    button.textContent = "发送中...";
    const pendingIndicator = appendPendingIndicator();

    try {
      let response;
      for (let attempt = 0; attempt < 2; attempt += 1) {
        try {
          response = await fetch("/chat", {
            method: "POST",
            headers: {
              "Content-Type": "application/json",
            },
            body: JSON.stringify({
              session_id: sessionId,
              message,
              history: conversationHistory,
            }),
          });
          if (!response.ok) {
            throw new Error(`http_${response.status}`);
          }
          break;
        } catch (error) {
          if (attempt === 1) throw error;
          await new Promise((resolve) => setTimeout(resolve, 500));
        }
      }

      const data = await response.json();
      pendingIndicator.remove();
      appendMessage(
        "assistant",
        data.degraded ? "TingT 分身（降级）" : "TingT 分身",
        data.reply
      );
      pushHistory("assistant", data.reply);
    } catch (error) {
      pendingIndicator.remove();
      appendMessage("assistant", "TingT 分身（网络重试失败）", NETWORK_FALLBACK);
    } finally {
      button.disabled = false;
      button.textContent = "发送";
      input.focus();
    }
  }

  input.addEventListener("input", autosize);
  input.addEventListener("keydown", function (event) {
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      if (!button.disabled) {
        form.requestSubmit();
      }
    }
  });

  form.addEventListener("submit", onSubmit);
  autosize();
})();

(() => {
  const main = document.querySelector(".main-content");
  const usage = document.querySelector(".usage-meter");
  const dock = document.querySelector("#answer-dock");
  const dockContent = dock?.querySelector(".answer-dock-content");
  const pendingForms = new WeakSet();
  const activeRequests = new Map();
  if (!main || !usage || !dock || !dockContent) return;

  const isLocal = (url) => url.origin === window.location.origin;
  const isAnswerForm = (form) => form.dataset.target === "answer";
  const targetFor = (answer) => answer ? dockContent : main;

  function formDataWithSubmitter(form, submitter) {
    try {
      return new FormData(form, submitter || undefined);
    } catch (_) {
      const data = new FormData(form);
      if (submitter?.name) data.append(submitter.name, submitter.value);
      return data;
    }
  }

  function setLoading(form, message) {
    form.querySelectorAll(".local-request-status, .local-request-error").forEach((node) => node.remove());
    const status = document.createElement("span");
    status.className = "local-request-status";
    const spinner = document.createElement("span");
    spinner.className = "local-request-spinner";
    const label = document.createElement("span");
    label.textContent = message;
    status.append(spinner, label);
    form.insertAdjacentElement("afterend", status);
    return status;
  }

  function setTargetLoading(anchor, destination, message) {
    if (anchor.isConnected && destination.contains(anchor)) return setLoading(anchor, message);
    const status = document.createElement("div");
    status.className = "local-request-status";
    const spinner = document.createElement("span");
    spinner.className = "local-request-spinner";
    const label = document.createElement("span");
    label.textContent = message;
    status.append(spinner, label);
    destination.prepend(status);
    return status;
  }

  function showError(anchor, destination, message, retry) {
    destination.querySelectorAll(".local-request-status, .local-request-error").forEach((node) => node.remove());
    const notice = document.createElement("div");
    notice.className = "local-request-error";
    const text = document.createElement("span");
    text.textContent = message;
    const button = document.createElement("button");
    button.type = "button";
    button.textContent = "Try again";
    button.addEventListener("click", retry, { once: true });
    notice.append(text, document.createTextNode(" "), button);
    if (anchor !== destination && anchor.isConnected && destination.contains(anchor)) anchor.insertAdjacentElement("afterend", notice);
    else destination.prepend(notice);
  }

  function updateBodyScale(responseDocument) {
    const classes = [...responseDocument.body.classList].filter((name) => name.startsWith("scale-") || name.startsWith("width-"));
    document.body.classList.remove(...[...document.body.classList].filter((name) => name.startsWith("scale-") || name.startsWith("width-")));
    document.body.classList.add(...classes);
  }

  function swapResponse(html, answer) {
    const parsed = new DOMParser().parseFromString(html, "text/html");
    const incomingMain = parsed.querySelector(".main-content");
    const incomingUsage = parsed.querySelector(".usage-meter");
    if (!incomingMain || !incomingUsage) throw new Error("The server returned an incomplete page.");

    const destination = targetFor(answer);
    if (answer) {
      dockContent.replaceChildren(...[...incomingMain.childNodes].map((node) => node.cloneNode(true)));
      document.body.classList.add("answer-is-open");
      if (window.innerWidth <= 900) dock.scrollIntoView({ block: "nearest" });
    } else {
      const scrollTop = window.scrollY;
      const openIds = [...main.querySelectorAll("details[open][id]")].map((item) => item.id);
      main.replaceChildren(...[...incomingMain.childNodes].map((node) => node.cloneNode(true)));
      openIds.forEach((id) => {
        const replacement = [...main.querySelectorAll("details[id]")].find((item) => item.id === id);
        if (replacement) replacement.open = true;
      });
      window.scrollTo(0, scrollTop);
    }
    usage.replaceChildren(...[...incomingUsage.childNodes].map((node) => node.cloneNode(true)));
    updateBodyScale(parsed);
    if (parsed.title) document.title = parsed.title;
    return parsed;
  }

  function refreshUrl(parsed, responseUrl) {
    const meta = parsed.querySelector('meta[http-equiv="refresh" i]');
    if (!meta) return null;
    const content = meta.getAttribute("content") || "";
    const match = content.match(/(?:^|;)\s*url\s*=\s*(?:'([^']*)'|"([^"]*)"|([^;]*))/i);
    const value = (match?.[1] || match?.[2] || match?.[3] || "").trim();
    if (!value) return null;
    const next = new URL(value, responseUrl);
    return isLocal(next) ? next : null;
  }

  async function requestAndRender(form, method, action, data, answer, status, polling = false) {
    if (form instanceof HTMLFormElement && pendingForms.has(form)) return;
    if (form instanceof HTMLFormElement) pendingForms.add(form);
    const destination = targetFor(answer);
    const previousController = activeRequests.get(destination);
    previousController?.abort();
    const controller = new AbortController();
    activeRequests.set(destination, controller);
    destination.querySelectorAll(".local-request-status, .local-request-error").forEach((node) => {
      if (node !== status) node.remove();
    });
    const controls = form instanceof HTMLFormElement ? [...form.elements] : [...form.querySelectorAll("button, input")];
    const submitButtons = controls.filter((control) => control.matches('button[type="submit"], input[type="submit"], .video-check input, .archive-check'));
    const oldDisabled = submitButtons.map((button) => button.disabled);
    submitButtons.forEach((button) => { button.disabled = true; });
    let statusNode = status || setLoading(form, "Sending…");
    let hasRendered = false;
    let lastUrl = new URL(action, window.location.href);
    const retry = () => {
      const retryMethod = polling ? "GET" : method;
      const retryAction = polling ? lastUrl.href : action;
      const retryData = polling ? new FormData() : data;
      requestAndRender(form, retryMethod, retryAction, retryData, answer, setTargetLoading(form, destination, "Sending…"), polling);
    };

    try {
      let url = new URL(action, window.location.href);
      if (!isLocal(url)) throw new Error("Only same-site requests are supported.");
      let requestMethod = method.toUpperCase();
      let body;
      if (requestMethod === "GET") {
        const query = new URLSearchParams(url.search);
        for (const [key, value] of data.entries()) {
          if (typeof value === "string") query.append(key, value);
        }
        url.search = query.toString();
      } else {
        body = data;
      }
      lastUrl = url;

      while (url) {
        lastUrl = url;
        const response = await fetch(url.href, {
          method: requestMethod,
          body,
          credentials: "same-origin",
          headers: { Accept: "text/html" },
          signal: controller.signal,
        });
        if (response.url && !isLocal(new URL(response.url))) throw new Error("The request left this site.");
        const contentType = response.headers.get("content-type") || "";
        if (!contentType.toLowerCase().includes("text/html")) throw new Error("The server did not return an HTML page.");
        const html = await response.text();
        const parsed = new DOMParser().parseFromString(html, "text/html");
        if (!response.ok) {
          const notice = parsed.querySelector(".failure-notice p");
          throw new Error(notice?.textContent || `The request failed (${response.status}).`);
        }
        if (!parsed.querySelector(".main-content") || !parsed.querySelector(".usage-meter")) throw new Error("The server returned an incomplete page.");

        const nextUrl = refreshUrl(parsed, response.url || url.href);
        swapResponse(html, answer);
        hasRendered = true;
        if (nextUrl) {
          statusNode?.remove();
          statusNode = document.createElement("div");
          statusNode.className = "local-request-status";
          const spinner = document.createElement("span");
          spinner.className = "local-request-spinner";
          const label = document.createElement("span");
          label.textContent = "Working…";
          statusNode.append(spinner, label);
          targetFor(answer).prepend(statusNode);
        } else {
          statusNode?.remove();
          break;
        }
        url = nextUrl;
        requestMethod = "GET";
        body = undefined;
        polling = true;
        await new Promise((resolve) => window.setTimeout(resolve, 2000));
      }
      statusNode?.remove();
    } catch (error) {
      statusNode?.remove();
      if (!controller.signal.aborted) showError(hasRendered ? destination : form, destination, error instanceof Error ? error.message : "The request could not be completed.", retry);
    } finally {
      submitButtons.forEach((button, index) => { button.disabled = oldDisabled[index]; });
      if (form instanceof HTMLFormElement) pendingForms.delete(form);
      if (activeRequests.get(destination) === controller) activeRequests.delete(destination);
    }
  }

  document.addEventListener("submit", (event) => {
    const form = event.target;
    if (!(form instanceof HTMLFormElement) || form.dataset.localRequest === "off") return;
    const action = new URL(form.getAttribute("action") || window.location.href, window.location.href);
    if (!isLocal(action)) return;
    event.preventDefault();
    const method = (form.getAttribute("method") || "GET").toUpperCase();
    const data = formDataWithSubmitter(form, event.submitter);
    requestAndRender(form, method, action.href, data, isAnswerForm(form));
  });

  document.addEventListener("click", (event) => {
    const link = event.target.closest("a[href]");
    if (!link || !main.contains(link) || link.hasAttribute("download") || link.target === "_blank") return;
    if (event.defaultPrevented || event.button !== 0 || event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) return;
    const url = new URL(link.href, window.location.href);
    if (!isLocal(url) || (url.pathname === window.location.pathname && url.search === window.location.search && url.hash)) return;
    if (["/", "/archive", "/settings"].includes(url.pathname) && !url.search) return;
    event.preventDefault();
    const data = new FormData();
    requestAndRender(link, "GET", url.href, data, false);
  });

  // Let Python refresh the selection count after a title is checked.
  document.addEventListener("change", (event) => {
    if (event.target.matches('.video-check input[name="video_ids"]')) {
      event.target.form.requestSubmit();
    }
  });

  dock.querySelector(".answer-dock-close")?.addEventListener("click", () => {
    activeRequests.get(dockContent)?.abort();
    activeRequests.delete(dockContent);
    document.body.classList.remove("answer-is-open");
  });
})();

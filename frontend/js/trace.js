/* trace.js
   Agent Communication Log panel.
   Depends on: nothing (standalone module).
   Public API: traceApp.render(agentTrace, workingMemory)
               traceApp.open() / traceApp.close() / traceApp.toggle()
*/

const traceApp = (() => {

    // ── Agent → icon / key mapping ───────────────────────────────────────
    const AGENT_META = {
        "Router Agent":       { key: "router",  icon: "fa-route" },
        "Web Search Agent":   { key: "web",     icon: "fa-globe" },
        "RAG Agent":          { key: "rag",     icon: "fa-book-open" },
        "Summary Agent":      { key: "summary", icon: "fa-file-pen" },
        "Report Writer Agent":{ key: "writer",  icon: "fa-file-lines" },
    };

    function _agentKey(name) {
        return (AGENT_META[name] || {}).key || "unknown";
    }
    function _agentIcon(name) {
        return (AGENT_META[name] || {}).icon || "fa-robot";
    }

    // ── DOM refs (set after DOMContentLoaded) ─────────────────────────────
    let _panel   = null;
    let _body    = null;
    let _badge   = null;
    let _footer  = null;
    let _memStrip = null;

    // ── Public: open / close / toggle ─────────────────────────────────────
    function open()   { _panel && _panel.classList.add("open"); }
    function close()  { _panel && _panel.classList.remove("open"); }
    function toggle() { _panel && _panel.classList.toggle("open"); }
    function isOpen() { return _panel && _panel.classList.contains("open"); }

    // ── Public: render a new trace result ─────────────────────────────────
    function render(agentTrace, workingMemory) {
        if (!_body) return;

        // Update badge count on the toggle button
        const count = (agentTrace || []).length;
        if (_badge) _badge.textContent = count;

        // Render memory strip
        _renderMemory(workingMemory || {});

        // Render steps
        _body.innerHTML = "";

        if (!agentTrace || agentTrace.length === 0) {
            _body.innerHTML = `
                <div class="trace-empty">
                    <i class="fa-solid fa-diagram-project"></i>
                    <p>No agent trace yet. Send a message to see how agents collaborate.</p>
                </div>`;
            _updateFooter(0, 0);
            return;
        }

        let totalMs = 0;
        agentTrace.forEach((step, idx) => {
            totalMs += (step.duration_ms || 0);
            _body.appendChild(_buildStep(step, idx));
        });

        _updateFooter(agentTrace.length, totalMs);

        // Auto-open panel on first real trace
        if (count > 0 && !isOpen()) open();
    }

    // ── Build one step card ────────────────────────────────────────────────
    function _buildStep(step, idx) {
        const agentKey  = _agentKey(step.agent);
        const agentIcon = _agentIcon(step.agent);
        const ms        = step.duration_ms || 0;
        const meta      = step.metadata || {};

        // Source pills (from RAG / web steps)
        const sources = meta.sources || [];
        const sourcePillsHTML = sources.length
            ? `<div class="trace-sources">
                ${sources.map(s => `<span class="trace-source-pill"><i class="fa-regular fa-file"></i> ${_esc(s)}</span>`).join("")}
               </div>`
            : "";

        // Serialised metadata block
        const metaJSON = JSON.stringify(meta, null, 2);
        const metaId   = `trace-meta-${idx}`;

        const div = document.createElement("div");
        div.className = "trace-step";
        div.setAttribute("data-agent", agentKey);
        div.style.animationDelay = `${idx * 60}ms`;

        div.innerHTML = `
            <div class="trace-step-icon">
                <i class="fa-solid ${agentIcon}"></i>
            </div>
            <div class="trace-step-body">
                <div class="trace-step-top">
                    <span class="trace-step-agent">${_esc(step.agent)}</span>
                    <span class="trace-step-ms">${ms} ms</span>
                </div>
                <div class="trace-step-action">${_esc(step.action)}</div>
                <div class="trace-step-output">${_esc(step.output)}</div>
                ${sourcePillsHTML}
                <button class="trace-step-expand" onclick="traceApp._toggleMeta('${metaId}', this)">
                    <i class="fa-solid fa-chevron-down"></i> Details
                </button>
                <pre class="trace-step-meta" id="${metaId}">${_esc(metaJSON)}</pre>
            </div>`;

        return div;
    }

    // ── Toggle metadata pre block ──────────────────────────────────────────
    function _toggleMeta(id, btn) {
        const pre = document.getElementById(id);
        if (!pre) return;
        const visible = pre.classList.toggle("visible");
        btn.innerHTML = visible
            ? `<i class="fa-solid fa-chevron-up"></i> Hide`
            : `<i class="fa-solid fa-chevron-down"></i> Details`;
    }

    // ── Render working memory strip ────────────────────────────────────────
    function _renderMemory(mem) {
        if (!_memStrip) return;
        const keys = Object.keys(mem);
        if (keys.length === 0) {
            _memStrip.innerHTML = `
                <div class="trace-memory-label"><i class="fa-solid fa-brain"></i> Working Memory</div>
                <span class="trace-memory-empty">Empty — will populate as agents run.</span>`;
            return;
        }

        const pills = keys.map(k => {
            let val = mem[k];
            if (Array.isArray(val)) val = val.slice(-3).join(", ") || "—";
            else if (typeof val === "object") val = JSON.stringify(val);
            else val = String(val);
            if (val.length > 40) val = val.slice(0, 38) + "…";
            return `<span class="trace-memory-pill"><strong>${_esc(k)}:</strong> ${_esc(val)}</span>`;
        }).join("");

        _memStrip.innerHTML = `
            <div class="trace-memory-label"><i class="fa-solid fa-brain"></i> Working Memory</div>
            <div class="trace-memory-pills">${pills}</div>`;
    }

    // ── Footer total ───────────────────────────────────────────────────────
    function _updateFooter(steps, totalMs) {
        if (!_footer) return;
        _footer.innerHTML = `
            <span class="trace-footer-total">
                <i class="fa-solid fa-diagram-project"></i>
                ${steps} agent step${steps !== 1 ? "s" : ""}
            </span>
            <span>${totalMs} ms total</span>`;
    }

    // ── HTML escape ────────────────────────────────────────────────────────
    function _esc(str) {
        return String(str).replace(/[&<>"']/g, c => ({
            "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;"
        }[c]));
    }

    // ── Init on DOMContentLoaded ───────────────────────────────────────────
    function init() {
        _panel    = document.getElementById("trace-panel");
        _body     = document.getElementById("trace-body");
        _badge    = document.getElementById("trace-badge");
        _footer   = document.getElementById("trace-footer");
        _memStrip = document.getElementById("trace-memory-strip");

        if (!_panel) return;

        // Close when clicking outside on mobile
        document.addEventListener("click", (e) => {
            if (isOpen()
                && !_panel.contains(e.target)
                && !e.target.closest(".trace-toggle-btn")) {
                close();
            }
        });
    }

    document.addEventListener("DOMContentLoaded", init);

    // Public surface
    return { open, close, toggle, isOpen, render, _toggleMeta };

})();

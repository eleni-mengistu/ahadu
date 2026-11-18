function readSetting(key, fallback) {
  try { return localStorage.getItem(key) || fallback; } catch (_) { return fallback; }
}

function saveSetting(key, value) {
  try { localStorage.setItem(key, value); } catch (_) {}
}

function shell() {
  return {
    drawer: false,
    finder: false,
    appearance: false,
    query: "",
    cursor: 0,
    theme: readSetting("zu-theme", "light"),
    accent: readSetting("zu-accent", "burgundy"),
    items: JSON.parse(document.getElementById("palette-data").textContent),
    get results() {
      const q = this.query.trim().toLowerCase();
      return (q ? this.items.filter((i) => (i.label + " " + i.hint).toLowerCase().includes(q)) : this.items).slice(0, 8);
    },
    setTheme(value) {
      this.theme = value;
      document.documentElement.dataset.theme = value;
      saveSetting("zu-theme", value);
    },
    setAccent(value) {
      this.accent = value;
      document.documentElement.dataset.accent = value;
      saveSetting("zu-accent", value);
    },
    clearChat() {
      try { sessionStorage.clear(); } catch (_) {}
    },
    openFinder() {
      this.finder = true; this.query = ""; this.cursor = 0;
      setTimeout(() => this.$refs.finderInput.focus(), 50);
    },
    keys(event) {
      if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === "k") {
        event.preventDefault();
        this.finder ? (this.finder = false) : this.openFinder();
      } else if (event.key === "Escape") {
        this.finder = false; this.drawer = false; this.appearance = false;
      }
    },
    move(step) {
      const size = this.results.length;
      if (size) this.cursor = (this.cursor + step + size) % size;
    },
    go() {
      const hit = this.results[this.cursor];
      if (hit) window.location.href = hit.href;
    },
  };
}

function assistant() {
  const config = JSON.parse(document.getElementById("assistant-config").textContent);
  const storeKey = "zu-chat-" + config.key;
  return {
    ...config,
    open: false,
    busy: false,
    draft: "",
    messages: [],
    init() {
      try { this.messages = JSON.parse(sessionStorage.getItem(storeKey) || "[]"); } catch (_) { this.messages = []; }
    },
    persist() {
      try { sessionStorage.setItem(storeKey, JSON.stringify(this.messages.slice(-30))); } catch (_) {}
    },
    toggle() {
      this.open = !this.open;
      if (this.open) this.$nextTick(() => { this.scroll(); setTimeout(() => this.$refs.chatInput.focus(), 60); });
    },
    scroll() {
      const box = this.$refs.chatLog;
      if (box) box.scrollTop = box.scrollHeight;
    },
    reset() { this.messages = []; this.persist(); },
    isExternal(href) { return href.startsWith("http"); },
    async send(text) {
      const message = (text ?? this.draft).trim();
      if (!message || this.busy) return;
      const history = this.messages.map((m) => ({ role: m.role, content: m.content }));
      this.messages.push({ role: "user", content: message });
      this.draft = "";
      this.busy = true;
      this.$nextTick(() => this.scroll());
      try {
        const response = await fetch("/api/assistant", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ message, history }),
        });
        if (response.status === 401) throw new Error("expired");
        if (!response.ok) throw new Error("failed");
        const reply = await response.json();
        this.messages.push({ role: "assistant", content: reply.reply, links: reply.links || [] });
      } catch (error) {
        this.messages.push({ role: "assistant", content: error.message === "expired" ? this.text.expired : this.text.error, links: [] });
      }
      this.busy = false;
      this.persist();
      this.$nextTick(() => { this.scroll(); this.$refs.chatInput.focus(); });
    },
  };
}

function gpaCalc() {
  const data = JSON.parse(document.getElementById("gpa-data").textContent);
  return {
    ...data,
    target: 3.0,
    get byLetter() { return Object.fromEntries(this.grades.map((g) => [g.letter, g])); },
    get result() {
      let points = this.basePoints, credits = this.baseCredits, termPoints = 0, termCredits = 0, planned = 0;
      for (const course of this.courses) {
        const grade = this.byLetter[course.grade];
        if (!grade) continue;
        planned += 1;
        points += grade.points * course.credits;
        credits += course.credits;
        termPoints += grade.points * course.credits;
        termCredits += course.credits;
        if (course.priorFail && grade.passes) credits -= course.priorFail.credits;
      }
      return {
        planned,
        gpa: credits ? points / credits : null,
        term: termCredits ? termPoints / termCredits : null,
        credits,
      };
    },
    get change() {
      if (this.result.gpa === null || this.currentGpa === null) return null;
      return this.result.gpa - this.currentGpa;
    },
    get needed() {
      let credits = this.baseCredits, term = 0;
      for (const course of this.courses) {
        term += course.credits;
        credits += course.credits - (course.priorFail ? course.priorFail.credits : 0);
      }
      return term ? (Number(this.target) * credits - this.basePoints) / term : null;
    },
    fmt(value) { return value === null || Number.isNaN(value) ? "–" : value.toFixed(2); },
    useEstimates() { this.courses.forEach((c) => { c.grade = c.suggested; }); },
    setAll(letter) { this.courses.forEach((c) => { c.grade = letter; }); },
  };
}

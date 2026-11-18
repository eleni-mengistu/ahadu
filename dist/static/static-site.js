/* Used only by the static Netlify build, where no Python server is running. */
(function () {
  const SALT = "zu-sap-static-v1";
  const arabic = document.documentElement.lang === "ar";
  const MESSAGES = {
    id: arabic ? "لم نجد هذا الرقم الجامعي. تأكد من الرقم وحاول مجددا." : "We can't find that student ID. Check the number and try again.",
    password: arabic ? "كلمة المرور غير صحيحة. حاول مرة أخرى." : "That password is incorrect. Please try again.",
    failed: arabic ? "تعذر تسجيل الدخول. حاول مرة أخرى." : "We couldn't sign you in. Please try again.",
  };

  async function sha256(text) {
    const bytes = await crypto.subtle.digest("SHA-256", new TextEncoder().encode(text));
    return [...new Uint8Array(bytes)].map((b) => b.toString(16).padStart(2, "0")).join("");
  }

  function showError(form, text) {
    let box = form.querySelector("[data-login-error]");
    if (!box) {
      box = document.createElement("div");
      box.className = "alert-row alert-danger mb-4";
      box.setAttribute("role", "alert");
      box.dataset.loginError = "";
      box.innerHTML = '<div class="text-sm font-medium"></div>';
      form.insertBefore(box, form.querySelector("label"));
    }
    box.firstChild.textContent = text;
    if (window.Alpine) window.Alpine.$data(form).busy = false;
  }

  const form = document.querySelector("form[data-static-login]");
  if (form) {
    form.addEventListener("submit", async (event) => {
      event.preventDefault();
      const id = form.student_id.value.trim();
      const language = arabic ? "ar" : "en";
      try {
        const known = await (await fetch("/auth-ids.json")).json();
        if (!known.includes(await sha256(`${SALT}|${id}`))) return showError(form, MESSAGES.id);
        const token = (await sha256(`${SALT}|${id}|${form.password.value}`)).slice(0, 32);
        const target = `/s/${token}/${language}/`;
        const found = await fetch(`${target}index.html`, { method: "HEAD" });
        if (!found.ok) return showError(form, MESSAGES.password);
        window.location.href = target;
      } catch (_) {
        showError(form, MESSAGES.failed);
      }
    });
  }

  const match = location.pathname.match(/^\/s\/[a-f0-9]{32}\/(en|ar)\//);
  if (!match) return;
  let student, rules;

  function normalize(text) {
    return text.toLowerCase().replace(/[ً-ٟـ]/g, "").replace(/[أإآ]/g, "ا")
      .replace(/ة/g, "ه").replace(/ى/g, "ي").replace(/ؤ/g, "و").replace(/ئ/g, "ي");
  }

  function hasKeyword(text, word) {
    if (/^[a-z ]+$/.test(word)) return new RegExp(`\\b${word}`).test(text);
    return text.includes(word);
  }

  window.zuAnswer = async function (message, pageLanguage) {
    student = student || await (await fetch(`${match[0]}assistant.json`)).json();
    rules = rules || await (await fetch("/assistant-rules.json")).json();
    const language = /[؀-ۿ]/.test(message) ? "ar" : /[A-Za-z]{3}/.test(message) ? "en" : pageLanguage;
    const set = student[language];
    const text = normalize(message);
    const compact = text.replace(/[\s-]/g, "");
    const intent = (rules.intents.find(([, words]) => words.some((w) => hasKeyword(text, w))) || [])[0];
    let course = student.courses.find((c) => compact.includes(c.code.toLowerCase()));
    if (!course && !rules.noTitleMatch.includes(intent)) course = student.courses.find((c) => c.names.some((n) => text.includes(n)));
    if (course && intent !== "thanks") return set.courses[course.code];
    const day = rules.days.find(([, names]) => names.some((n) => text.includes(n)));
    if (day) return set.days[day[0]];
    return set.intents[intent] || set.fallback;
  };
})();

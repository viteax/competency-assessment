// Точка входа: вход в систему, меню по роли, тема оформления.

import { adminAssign } from "./admin/assign.js";
import { adminCatalogs } from "./admin/catalogs.js";
import { adminImport } from "./admin/import.js";
import { adminQuestions } from "./admin/questions.js";
import { adminGroupResults, adminLaborFunctions } from "./admin/results.js";
import { adminStudents } from "./admin/students.js";
import { api, errorBox, fill, go, h, render, session, setMenu } from "./core.js";
import { studentResults, studentTests } from "./student.js";

const ADMIN_MENU = [
  ["Назначить тест", adminAssign],
  ["Студенты", adminStudents],
  ["Результаты группы", adminGroupResults],
  ["ПК → ОТФ", adminLaborFunctions],
  ["Банк вопросов", adminQuestions],
  ["Справочники", adminCatalogs],
  ["Импорт", adminImport],
];

const STUDENT_MENU = [
  ["Мои тесты", studentTests],
  ["Мои результаты", studentResults],
];

const who = document.getElementById("who");

function logout() {
  session.token = null;
  showLogin();
}

function showLogin() {
  setMenu([]);
  fill(document.getElementById("nav"));
  fill(who);
  const err = errorBox();
  const username = h("input", { type: "text", autocomplete: "username", required: true });
  const password = h("input", { type: "password", autocomplete: "current-password", required: true });
  render(
    h(
      "form",
      {
        class: "card login",
        onsubmit: async (event) => {
          event.preventDefault();
          err.clear();
          try {
            const data = await api("/auth/token", {
              method: "POST",
              form: { username: username.value, password: password.value },
            });
            session.token = data.access_token;
            await start();
          } catch (e) {
            err.show(e);
          }
        },
      },
      h("h1", {}, "Вход"),
      h("label", {}, "Логин"),
      username,
      h("label", {}, "Пароль"),
      password,
      h("div", { style: "margin-top:16px" }, h("button", { class: "primary" }, "Войти")),
      err.el,
    ),
  );
}

async function start() {
  if (!session.token) return showLogin();
  let me;
  try {
    me = await api("/me");
  } catch {
    return logout();
  }
  fill(who,
    `${me.username} (${me.role === "admin" ? "администратор" : "студент"}) `,
    h("button", { class: "link", onclick: logout }, "Выйти"),
  );
  const menu = me.role === "admin" ? ADMIN_MENU : STUDENT_MENU;
  setMenu(menu);
  await go(menu[0][1]);
}

// --- тема оформления -----------------------------------------------------------

const THEMES = [
  ["auto", "◐ Тема: как в системе"],
  ["light", "☀ Тема: светлая"],
  ["dark", "☾ Тема: тёмная"],
];
const themeButton = document.getElementById("theme");

function applyTheme(theme) {
  if (theme === "auto") delete document.documentElement.dataset.theme;
  else document.documentElement.dataset.theme = theme;
  try { localStorage.setItem("theme", theme); } catch { /* приватный режим */ }
  themeButton.textContent = THEMES.find(([t]) => t === theme)[1];
  themeButton.dataset.value = theme;
}

themeButton.addEventListener("click", () => {
  const i = THEMES.findIndex(([t]) => t === themeButton.dataset.value);
  applyTheme(THEMES[(i + 1) % THEMES.length][0]);
});
applyTheme(document.documentElement.dataset.theme || "auto");

// -------------------------------------------------------------------------------

window.addEventListener("unhandledrejection", (event) => {
  const box = errorBox();
  box.show(event.reason);
  document.getElementById("app").prepend(box.el);
});

session.onUnauthorized(logout);
start();

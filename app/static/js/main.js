// Точка входа: вход в систему, меню по роли, тема оформления.

import { adminAssign } from "./admin/assign.js";
import { adminAudit } from "./admin/audit.js";
import { adminCatalogs } from "./admin/catalogs.js";
import { adminImport } from "./admin/import.js";
import { adminQuestions } from "./admin/questions.js";
import { adminGroupResults, adminLaborFunctions } from "./admin/results.js";
import { adminStudents } from "./admin/students.js";
import { adminTests } from "./admin/tests.js";
import { api, errorBox, fill, go, h, render, setMenu, setUnauthorizedHandler } from "./core.js";
import { studentResults, studentTests } from "./student.js";
import { teacherDisciplines } from "./teacher.js";

const ADMIN_MENU = [
  ["Назначить тест", adminAssign],
  ["Тесты", adminTests],
  ["Студенты", adminStudents],
  ["Результаты группы", adminGroupResults],
  ["ПК → ОТФ", adminLaborFunctions],
  ["Банк вопросов", adminQuestions],
  ["Справочники", adminCatalogs],
  ["Импорт", adminImport],
  ["Журнал", adminAudit],
];

const TEACHER_MENU = [["Мои дисциплины", teacherDisciplines]];
const ROLE_NAMES = { admin: "администратор", teacher: "преподаватель", student: "студент" };

const STUDENT_MENU = [
  ["Мои тесты", studentTests],
  ["Мои результаты", studentResults],
];

const who = document.getElementById("who");

async function logout() {
  try {
    await api("/auth/logout", { method: "POST" });
  } finally {
    showLogin();
  }
}

function clearHeader() {
  setMenu([]);
  fill(document.getElementById("nav"));
  fill(who);
}

function showLogin(message) {
  clearHeader();
  const err = errorBox();
  if (message) err.show(new Error(message));
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
            await login(username.value, password.value);
            await start();
          } catch (e) {
            err.show(e);
          }
        },
      },
      h("h1", {}, "Вход"),
      h("label", {}, "Логин или ФИО"),
      username,
      h("label", {}, "Пароль"),
      password,
      h("div", { style: "margin-top:16px" }, h("button", { class: "primary" }, "Войти")),
      err.el,
      h("p", { class: "muted small", style: "margin-top:16px" },
        "Студент и ещё нет учётной записи? ",
        h("button", { type: "button", class: "link", style: "padding:0", onclick: showRegistration }, "Зарегистрироваться")),
    ),
  );
}

// Регистрация студента: ФИО сверяется со списком группы, пароль – свой.
async function showRegistration() {
  clearHeader();
  const err = errorBox();
  const groups = await api("/auth/groups").catch(() => []);
  const group = h("select", { required: true, "aria-label": "Группа" },
    h("option", { value: "" }, "– выберите группу –"),
    groups.map((g) => h("option", { value: g.id }, g.name)));
  const fullName = h("input", { type: "text", required: true, autocomplete: "name", "aria-label": "ФИО полностью" });
  const field = () => h("input", { type: "password", autocomplete: "new-password", required: true, minlength: 8 });
  const password = field();
  const repeat = field();
  render(
    h("form", {
      class: "card login",
      onsubmit: async (event) => {
        event.preventDefault();
        err.clear();
        if (password.value !== repeat.value) return err.show(new Error("пароли не совпадают"));
        try {
          const { username } = await api("/auth/register", {
            method: "POST",
            body: { group_id: Number(group.value), full_name: fullName.value, password: password.value },
          });
          await login(username, password.value);
          await start();
        } catch (e) {
          err.show(e);
        }
      },
    },
      h("h1", {}, "Регистрация студента"),
      h("p", { class: "muted small", style: "margin-top:0" }, "Выберите свою группу и введите ФИО полностью, как в списке группы. Потом входите по ФИО и этому паролю."),
      h("label", {}, "Группа"), group,
      h("label", {}, "ФИО полностью"), fullName,
      h("label", {}, "Пароль (не короче 8 символов)"), password,
      h("label", {}, "Пароль ещё раз"), repeat,
      h("div", { style: "margin-top:16px" }, h("button", { class: "primary" }, "Зарегистрироваться")),
      err.el,
      h("p", { class: "muted small", style: "margin-top:16px" },
        h("button", { type: "button", class: "link", style: "padding:0", onclick: () => showLogin() }, "← Уже есть учётная запись – войти")),
    ),
  );
}

// Сервер ставит httpOnly-cookie сессии; сам токен интерфейсу не нужен.
function login(username, password) {
  return api("/auth/token", { method: "POST", form: { username, password } });
}

// Смена пароля. Сервер завершает все сеансы, поэтому сразу входим с новым паролем.
function showPasswordChange(me, { forced }) {
  if (forced) clearHeader();
  const err = errorBox();
  const field = (autocomplete) =>
    h("input", { type: "password", autocomplete, required: true, minlength: 8 });
  const current = field("current-password");
  const next = field("new-password");
  const repeat = field("new-password");
  render(
    h("form", {
      class: "card login",
      onsubmit: async (event) => {
        event.preventDefault();
        err.clear();
        if (next.value !== repeat.value) return err.show(new Error("пароли не совпадают"));
        try {
          await api("/me/password", {
            method: "POST",
            body: { current_password: current.value, new_password: next.value },
          });
          await login(me.username, next.value);
          await start();
        } catch (e) {
          err.show(e);
        }
      },
    },
      h("h1", {}, forced ? "Задайте свой пароль" : "Смена пароля"),
      forced
        ? h("p", { class: "muted" }, "Вы вошли с временным паролем, который выдал администратор. Придумайте свой — не короче 8 символов.")
        : null,
      h("label", {}, forced ? "Временный пароль" : "Текущий пароль"), current,
      h("label", {}, "Новый пароль"), next,
      h("label", {}, "Новый пароль ещё раз"), repeat,
      h("div", { class: "row", style: "margin-top:16px" },
        h("button", { class: "primary" }, "Сохранить"),
        forced ? h("button", { type: "button", onclick: logout }, "Выйти") : h("button", { type: "button", onclick: start }, "Отмена"),
      ),
      err.el,
    ),
  );
}

async function start() {
  const me = await api("/auth/session").catch(() => null);
  if (!me) return showLogin();
  if (me.must_change_password) return showPasswordChange(me, { forced: true });
  fill(who,
    `${me.full_name || me.username} (${ROLE_NAMES[me.role]}) `,
    h("button", { class: "link", onclick: () => showPasswordChange(me, { forced: false }) }, "Сменить пароль"),
    h("button", { class: "link", onclick: logout }, "Выйти"),
  );
  const menu = { admin: ADMIN_MENU, teacher: TEACHER_MENU, student: STUDENT_MENU }[me.role];
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

setUnauthorizedHandler(() => showLogin("Сессия завершилась — войдите снова."));
start();

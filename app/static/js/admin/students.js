// Студенты группы и их учётные записи: добавление, правка, сброс пароля, удаление.

import { api, errorBox, fill, h, passwordNotice, temporaryPassword } from "../core.js";

export async function adminStudents(render) {
  const groups = await api("/groups");
  const groupNames = new Map(groups.map((g) => [g.id, g.name]));
  const group = h("select", {}, groups.map((g) => h("option", { value: g.id }, g.name)));
  const table = h("div", { class: "table-wrap" });
  const notice = h("div");
  const editSlot = h("div");
  const err = errorBox();

  async function action(fn) {
    err.clear();
    try {
      await fn();
    } catch (e) {
      err.show(e);
    }
  }

  function openEdit(student) {
    const fullName = h("input", { type: "text", required: true, value: student.full_name });
    const email = h("input", { type: "text", value: student.email || "" });
    const groupSelect = h("select", {}, groups.map((g) => h("option", { value: g.id }, g.name)));
    groupSelect.value = String(student.group_id);
    const formErr = errorBox();
    fill(editSlot, h("form", {
      class: "card edit-form",
      onsubmit: async (event) => {
        event.preventDefault();
        try {
          await api(`/students/${student.id}`, {
            method: "PUT",
            body: {
              full_name: fullName.value.trim(),
              group_id: Number(groupSelect.value),
              email: email.value.trim() || null,
              external_id: student.external_id,
            },
          });
          fill(editSlot);
          await drawStudents();
        } catch (e) {
          formErr.show(e);
        }
      },
    },
      h("h2", { style: "margin-top:0" }, "Изменить студента"),
      h("label", {}, "ФИО"), fullName,
      h("div", { class: "row" },
        h("div", {}, h("label", {}, "Группа"), groupSelect),
        h("div", {}, h("label", {}, "E-mail"), email),
      ),
      h("div", { class: "row", style: "margin-top:16px" },
        h("button", { class: "primary" }, "Сохранить"),
        h("button", { type: "button", onclick: () => fill(editSlot) }, "Отмена"),
      ),
      formErr.el,
    ));
    editSlot.scrollIntoView({ behavior: "smooth", block: "nearest" });
  }

  async function drawStudents() {
    const [students, users] = await Promise.all([
      api(`/students?group_id=${group.value}`),
      api("/users"),
    ]);
    const accounts = new Map(users.filter((u) => u.student_id).map((u) => [u.student_id, u]));
    fill(table,
      students.length
        ? h("table", {},
            h("tr", {}, ["ФИО", "E-mail", "Логин", ""].map((t) => h("th", {}, t))),
            students.map((s) => {
              const account = accounts.get(s.id);
              return h("tr", {},
                h("td", { class: "wrap" }, s.full_name),
                h("td", {}, s.email || h("span", { class: "muted" }, "–")),
                h("td", {},
                  account ? account.username : h("span", { class: "muted" }, "нет учётки"),
                  account?.must_change_password ? h("span", { class: "badge warn", style: "margin-left:6px" }, "не входил") : null,
                  account && !account.must_change_password && account.created_at
                    ? h("div", { class: "muted small" }, `создана ${new Date(account.created_at).toLocaleDateString("ru-RU")}`)
                    : null,
                ),
                h("td", { class: "actions" },
                  h("button", { class: "link", onclick: () => openEdit(s) }, "Изменить"),
                  account
                    ? h("button", {
                        class: "link",
                        onclick: () => action(async () => {
                          if (!confirm(`Сбросить пароль для ${s.full_name}? Текущий перестанет работать.`)) return;
                          const reset = await api(`/users/${account.id}/reset-password`, { method: "POST" });
                          fill(notice, passwordNotice(s.full_name, reset.username, reset.password));
                          await drawStudents();
                        }),
                      }, "Сбросить пароль")
                    : null,
                  h("button", {
                    class: "link danger",
                    onclick: () => action(async () => {
                      if (!confirm(`Удалить ${s.full_name} вместе с учётной записью?`)) return;
                      await api(`/students/${s.id}`, { method: "DELETE" });
                      await drawStudents();
                    }),
                  }, "Удалить"),
                ),
              );
            }),
          )
        : h("p", { class: "muted" }, `В группе ${groupNames.get(Number(group.value)) || ""} пока нет студентов`),
    );
  }
  group.addEventListener("change", () => { fill(editSlot); drawStudents(); });

  const fullName = h("input", { type: "text", required: true });
  const email = h("input", { type: "text" });
  const username = h("input", { type: "text", minlength: 3, pattern: "[A-Za-z0-9._\\-]+", title: "латиница, цифры, точка, дефис" });
  const addErr = errorBox();

  render(
    h("h1", {}, "Студенты"),
    h("div", { class: "card" },
      h("label", {}, "Группа"), group,
      err.el,
      notice,
      h("div", { style: "margin-top:12px" }, table),
    ),
    editSlot,
    h("form", {
      class: "card",
      onsubmit: async (event) => {
        event.preventDefault();
        addErr.clear();
        try {
          const student = await api("/students", {
            method: "POST",
            body: { full_name: fullName.value.trim(), group_id: Number(group.value), email: email.value.trim() || null },
          });
          if (username.value) {
            const password = temporaryPassword();
            await api("/users", {
              method: "POST",
              body: { username: username.value, password, role: "student", student_id: student.id },
            });
            fill(notice, passwordNotice(student.full_name, username.value, password));
          } else {
            fill(notice, h("div", { class: "notice" }, `${student.full_name} добавлен(а) без учётной записи: студент зарегистрируется сам по ФИО.`));
          }
          fullName.value = email.value = username.value = "";
          await drawStudents();
        } catch (e) {
          addErr.show(e);
        }
      },
    },
      h("h2", { style: "margin-top:0" }, "Добавить студента в выбранную группу"),
      h("p", { class: "muted small", style: "margin-top:0" }, "Если указать логин, сгенерируется временный пароль. Без логина студент зарегистрируется сам: выберет группу и введёт ФИО. Список группы удобнее загрузить во вкладке «Импорт»."),
      h("label", {}, "ФИО"), fullName,
      h("div", { class: "row" },
        h("div", {}, h("label", {}, "Логин (необязательно)"), username),
        h("div", {}, h("label", {}, "E-mail (необязательно)"), email),
      ),
      h("div", { style: "margin-top:16px" }, h("button", { class: "primary" }, "Добавить")),
      addErr.el,
    ),
  );
  if (groups.length) await drawStudents();
}

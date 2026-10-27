// Разделы администратора: страницы с вкладками. Порядок вкладок – порядок работы.

import { h, screenTab, tabbedPage } from "../core.js";
import { adminAssign } from "./assign.js";
import { CATALOGS } from "./catalogs.js";
import { competencyImportView, studentImportView } from "./import.js";
import { adminGroupResults, adminLaborFunctions } from "./results.js";
import { adminStudents } from "./students.js";
import { adminTests } from "./tests.js";

export const testsPage = tabbedPage("Тесты", {
  "Новый тест": screenTab(adminAssign),
  "Все тесты": screenTab(adminTests),
});

export const resultsPage = tabbedPage("Результаты", {
  "По группе": screenTab(adminGroupResults),
  "Трудовые функции студента": screenTab(adminLaborFunctions),
});

export const studentsPage = tabbedPage("Студенты", {
  "Список по группам": screenTab(adminStudents),
  "Загрузить из Excel / СДО": studentImportView,
});

// Пояснение над вкладкой справочников: что здесь хранится и на что влияет.
const intro = (text, tab) => async () => [h("p", { class: "muted" }, text), await tab()];

export const catalogsPage = tabbedPage("Справочники", {
  "Направления": intro("Направления подготовки кафедры: код и название, например 09.03.04 «Программная инженерия».", CATALOGS["Направления"]),
  "Группы": intro("Академические группы. Год набора нужен, чтобы считать текущий семестр группы.", CATALOGS["Группы"]),
  "Загрузка из ОПОП / РПД": intro("Самый быстрый старт: из файла ОПОП или РПД загружаются компетенции, а из РПД – еще и дисциплина с ее компетенциями.", competencyImportView),
  "Компетенции": intro("Компетенции ФГОС (УК, ОПК, ПК) с формулировками. Их проще загрузить из ОПОП или РПД – вкладка «Загрузка из ОПОП / РПД».", CATALOGS["Компетенции"]),
  "Дисциплины": intro("Дисциплины и компетенции, которые они формируют. По ним преподаватели составляют вопросы.", CATALOGS["Дисциплины"]),
  "Учебный план": CATALOGS["Учебный план"],
  "Преподаватели": intro("Учётные записи преподавателей. Дисциплины за ними закрепляются в «Учебном плане».", CATALOGS["Преподаватели"]),
  "Профстандарты": intro("Профессиональные стандарты, на которые ориентированы компетенции.", CATALOGS["Профстандарты"]),
  "ОТФ": intro("Обобщённые трудовые функции профстандартов.", CATALOGS["ОТФ"]),
  "ТФ ⇒ компетенции": CATALOGS["ТФ ⇒ компетенции"],
  "Настройки": CATALOGS["Настройки"],
}, "Учебный план");

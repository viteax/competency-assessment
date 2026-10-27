// Разделы администратора: страницы с вкладками. Порядок вкладок – порядок работы.

import { h, screenTab, tabbedPage } from "../core.js";
import { adminAssign } from "./assign.js";
import { CATALOGS } from "./catalogs.js";
import { directionTab } from "./directions.js";
import { competencyImportView, studentImportView } from "./import.js";
import { planImportView } from "./plan-import.js";
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
  "Загрузка УП": intro("Самый быстрый старт для направления: учебный план из «Планов» сразу заполняет направление, компетенции, дисциплины с семестрами и статусом, профстандарты и связи ТФ ⇒ компетенции.", planImportView),
  "Направления": intro("Направления подготовки кафедры: код и название, например 09.03.04 «Программная инженерия».", CATALOGS["Направления"]),
  "Группы": intro("Академические группы. Год набора нужен, чтобы считать текущий семестр группы.", CATALOGS["Группы"]),
  "Загрузка из ОПОП / РПД": intro("Индикаторы компетенций и компетенции дисциплины – из РПД; если учебного плана из «Планов» нет – и сами компетенции из ОПОП.", directionTab(competencyImportView)),
  "Компетенции": intro("Компетенции ФГОС (УК, ОПК, ПК) с формулировками. У каждого направления свои: коды в разных ОП совпадают, а формулировки бывают разные. Их проще загрузить из ОПОП или РПД – вкладка «Загрузка из ОПОП / РПД».", directionTab(CATALOGS["Компетенции"])),
  "Дисциплины": intro("Дисциплины направления, их статус в учебном плане и компетенции, которые они формируют. По ним преподаватели составляют вопросы.", directionTab(CATALOGS["Дисциплины"])),
  "Учебный план": directionTab(CATALOGS["Учебный план"]),
  "Преподаватели": intro("Учётные записи преподавателей. Дисциплины за ними закрепляются в «Учебном плане».", CATALOGS["Преподаватели"]),
  "Профстандарты": intro("Профессиональные стандарты, на которые ориентированы компетенции.", CATALOGS["Профстандарты"]),
  "ОТФ": intro("Обобщённые трудовые функции профстандартов.", CATALOGS["ОТФ"]),
  "ТФ ⇒ компетенции": directionTab(CATALOGS["ТФ ⇒ компетенции"]),
  "Настройки": CATALOGS["Настройки"],
}, "Учебный план");

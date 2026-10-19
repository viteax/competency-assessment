// ESLint для веб-интерфейса: ES-модули в браузере, без сборки.
import js from "@eslint/js";
import globals from "globals";

export default [
  js.configs.recommended,
  {
    files: ["app/static/**/*.js"],
    languageOptions: {
      ecmaVersion: 2024,
      sourceType: "module",
      globals: globals.browser,
    },
    rules: {
      "no-unused-vars": ["error", { args: "after-used", argsIgnorePattern: "^_" }],
      eqeqeq: ["error", "always"],
      "prefer-const": "error",
      "no-var": "error",
    },
  },
  {
    // theme-init.js подключается обычным скриптом до загрузки страницы.
    files: ["app/static/js/theme-init.js"],
    languageOptions: { sourceType: "script" },
  },
];

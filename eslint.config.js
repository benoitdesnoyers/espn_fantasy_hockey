import js from "@eslint/js";
import globals from "globals";

export default [
  { ignores: ["node_modules/", ".ha_config/"] },
  js.configs.recommended,
  {
    files: ["custom_components/**/frontend/**/*.js"],
    languageOptions: { globals: globals.browser },
  },
  {
    files: ["eslint.config.js"],
    languageOptions: { globals: globals.node },
  },
  {
    // Card tests run under Node against a stand-in DOM, so both sets apply.
    files: ["tests/frontend/**/*.js"],
    languageOptions: { globals: { ...globals.node, ...globals.browser } },
  },
  {
    rules: {
      eqeqeq: ["error", "always", { null: "ignore" }],
      "no-var": "error",
      "prefer-const": "error",
    },
  },
];

import { describe, expect, it } from "vitest";

import { catalogGroupLabels, languageOptions, translations } from "../i18n";

describe("localization catalog", () => {
  it("provides every interface key and catalog group for each selectable language", () => {
    const englishKeys = Object.keys(translations.en).sort();
    const englishCategoryKeys = Object.keys(translations.en.categories).sort();
    const englishGroupKeys = Object.keys(catalogGroupLabels.en).sort();

    for (const option of languageOptions) {
      expect(Object.keys(translations[option.id]).sort()).toEqual(englishKeys);
      expect(Object.keys(translations[option.id].categories).sort()).toEqual(englishCategoryKeys);
      expect(Object.keys(catalogGroupLabels[option.id]).sort()).toEqual(englishGroupKeys);
    }
  });
});

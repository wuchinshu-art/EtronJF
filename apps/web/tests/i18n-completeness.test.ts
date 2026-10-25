import { describe, it, expect } from 'vitest';
import { resources } from '../src/locales/i18n';

describe('四語字典缺 Key 深度自動化審查 (Deep i18n Key Completeness Check)', () => {
  const languages = ['zh-TW', 'ja-JP', 'en-US', 'zh-CN'] as const;

  // 遞迴取得物件所有扁平化鍵路徑 (例如 header.company, status.approved)
  function getDeepKeyPaths(obj: Record<string, any>, prefix = ''): string[] {
    let keys: string[] = [];
    for (const [k, v] of Object.entries(obj)) {
      const fullPath = prefix ? `${prefix}.${k}` : k;
      if (v !== null && typeof v === 'object' && !Array.isArray(v)) {
        keys = keys.concat(getDeepKeyPaths(v, fullPath));
      } else {
        keys.push(fullPath);
      }
    }
    return keys;
  }

  const baseKeys = getDeepKeyPaths(resources['zh-TW'].common).sort();

  for (const lang of languages) {
    if (lang === 'zh-TW') continue;

    it(`語系 [${lang}] 必須與基準語系 [zh-TW] 鍵值結構 100% 完全對齊，無任何缺漏鍵`, () => {
      const targetKeys = getDeepKeyPaths(resources[lang].common).sort();

      const missingInTarget = baseKeys.filter(k => !targetKeys.includes(k));
      const extraInTarget = targetKeys.filter(k => !baseKeys.includes(k));

      expect(
        missingInTarget,
        `語系 [${lang}] 缺少以下 Key: ${missingInTarget.join(', ')}`
      ).toEqual([]);

      expect(
        extraInTarget,
        `語系 [${lang}] 多出未定義的 Key: ${extraInTarget.join(', ')}`
      ).toEqual([]);
    });
  }
});

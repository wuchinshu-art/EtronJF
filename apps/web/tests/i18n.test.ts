import { describe, it, expect, beforeEach } from 'vitest';
import i18next from 'i18next';
import { initI18n, resources } from '../src/locales/i18n';

describe('i18n 多語系與四語完整性檢驗 (i18n Quad-language Completeness)', () => {
  beforeEach(async () => {
    await initI18n();
  });

  it('應確保四種語系 (zh-TW, ja-JP, en-US, zh-CN) 存在且鍵值結構對齊', () => {
    const requiredLanguages = ['zh-TW', 'ja-JP', 'en-US', 'zh-CN'] as const;
    const baseKeys = Object.keys(resources['zh-TW'].common);

    for (const lang of requiredLanguages) {
      expect(resources).toHaveProperty(lang);
      const langKeys = Object.keys(resources[lang].common);
      expect(langKeys.sort()).toEqual(baseKeys.sort());
    }
  });

  it('切換語言應能回傳正確翻譯字串', async () => {
    await i18next.changeLanguage('zh-TW');
    expect(i18next.t('appName')).toBe('ETJ 鈺創-福岡資訊管理系統');

    await i18next.changeLanguage('ja-JP');
    expect(i18next.t('appName')).toBe('ETJ エトロン福岡 情報管理システム');

    await i18next.changeLanguage('en-US');
    expect(i18next.t('appName')).toBe('ETJ Etron-Fukuoka Management System');

    await i18next.changeLanguage('zh-CN');
    expect(i18next.t('appName')).toBe('ETJ 钰创-福冈信息管理系统');
  });
});

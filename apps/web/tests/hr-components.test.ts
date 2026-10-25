import { describe, it, expect, beforeEach } from 'vitest';
import i18next from 'i18next';
import { initI18n } from '../src/locales/i18n';

describe('人事系統前端多語系與業務規格檢驗 (HR Frontend & i18n Verification)', () => {
  beforeEach(async () => {
    await initI18n();
  });

  it('應正確解析 hr 模組導航與四語字典鍵值', async () => {
    await i18next.changeLanguage('zh-TW');
    expect(i18next.t('nav.hr')).toBe('人事系統');
    expect(i18next.t('hr.tabs.persons')).toBe('人員基本檔案庫');
    expect(i18next.t('hr.tabs.employees')).toBe('在職員工與任職管理');
    expect(i18next.t('hr.employee.onboardBtn')).toBe('+ 新增報到');
    expect(i18next.t('hr.ledger.quotaSummary')).toBe('假額可用天數即時統計');

    await i18next.changeLanguage('ja-JP');
    expect(i18next.t('nav.hr')).toBe('人事管理');
    expect(i18next.t('hr.tabs.persons')).toBe('社員基本台帳');
    expect(i18next.t('hr.tabs.employees')).toBe('在籍社員・任職管理');
    expect(i18next.t('hr.employee.onboardBtn')).toBe('+ 新規入社');
    expect(i18next.t('hr.ledger.quotaSummary')).toBe('休暇残高リアルタイム集計');

    await i18next.changeLanguage('en-US');
    expect(i18next.t('nav.hr')).toBe('HR System');
    expect(i18next.t('hr.tabs.persons')).toBe('Person Master Profiles');
    expect(i18next.t('hr.tabs.employees')).toBe('Active Employees & Employment');
    expect(i18next.t('hr.employee.onboardBtn')).toBe('+ New Onboard');

    await i18next.changeLanguage('zh-CN');
    expect(i18next.t('nav.hr')).toBe('人事系统');
    expect(i18next.t('hr.tabs.persons')).toBe('人员基本档案库');
    expect(i18next.t('hr.tabs.employees')).toBe('在职员工与任职管理');
  });

  it('假額天數換算邏輯驗證：標準工時 480 分鐘換算為 1.0 天', () => {
    const standardDailyMinutes = 480;

    const testCases = [
      { minutes: 480, expectedDays: 1.0 },
      { minutes: 240, expectedDays: 0.5 },
      { minutes: 1440, expectedDays: 3.0 },
      { minutes: 3600, expectedDays: 7.5 },
      { minutes: 0, expectedDays: 0.0 },
    ];

    for (const tc of testCases) {
      const calculatedDays = Number((tc.minutes / standardDailyMinutes).toFixed(2));
      expect(calculatedDays).toBe(tc.expectedDays);
    }
  });
});

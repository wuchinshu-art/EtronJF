import { describe, it, expect, beforeEach } from 'vitest';
import { mount } from '@vue/test-utils';
import i18next from 'i18next';
import i18nextVue from 'i18next-vue';
import FilterBar from '../src/components/common/FilterBar.vue';
import { initI18n } from '../src/locales/i18n';

describe('營運儀表板搜尋與篩選功能檢驗 (Dashboard Filter & Search Verification)', () => {
  beforeEach(async () => {
    await initI18n();
    await i18next.changeLanguage('zh-TW');
  });

  const sampleRows = [
    {
      id: 1,
      docNo: 'LV-202610-0001',
      typeKey: 'leave',
      applicant: '王大明 (TW0102)',
      amount: '-',
      status: 'approved',
      utcTime: '2026-10-23T01:30:00Z',
    },
    {
      id: 2,
      docNo: 'EX-202610-0042',
      typeKey: 'expense',
      applicant: '佐藤健 (JP0088)',
      amount: '¥ 45,000',
      status: 'in_review',
      utcTime: '2026-10-23T02:15:00Z',
    },
    {
      id: 3,
      docNo: 'TR-202610-0019',
      typeKey: 'travel',
      applicant: '林雅婷 (TW0075)',
      amount: 'NT$ 12,500',
      status: 'submitted',
      utcTime: '2026-10-23T00:45:00Z',
    },
    {
      id: 4,
      docNo: 'SE-202610-0005',
      typeKey: 'seal',
      applicant: '陳冠宇 (TW0033)',
      amount: '-',
      status: 'returned',
      utcTime: '2026-10-22T08:00:00Z',
    },
  ];

  function filterRows(rows: typeof sampleRows, keyword: string) {
    const kw = keyword.trim().toLowerCase();
    if (!kw) return rows;
    return rows.filter((row) => {
      const typeLabel = i18next.t(`dashboard.types.${row.typeKey}`).toLowerCase();
      const statusLabel = i18next.t(`status.${row.status === 'in_review' ? 'inReview' : row.status}`).toLowerCase();
      return (
        row.docNo.toLowerCase().includes(kw) ||
        row.applicant.toLowerCase().includes(kw) ||
        row.amount.toLowerCase().includes(kw) ||
        typeLabel.includes(kw) ||
        statusLabel.includes(kw)
      );
    });
  }

  it('FilterBar 元件應正確觸發 search 與 reset 事件', async () => {
    const wrapper = mount(FilterBar, {
      props: {
        keywordPlaceholder: '搜尋單號、申請人...',
      },
      global: {
        plugins: [[i18nextVue, { i18next }]],
      },
    });

    const input = wrapper.find('input');
    await input.setValue('王大明');

    // 點擊查詢按鈕
    const buttons = wrapper.findAll('button');
    const searchBtn = buttons[0];
    const resetBtn = buttons[1];

    await searchBtn.trigger('click');
    expect(wrapper.emitted('search')).toBeTruthy();
    expect(wrapper.emitted('search')![0]).toEqual(['王大明']);

    // 點擊重設按鈕
    await resetBtn.trigger('click');
    expect(wrapper.emitted('reset')).toBeTruthy();
    expect(input.element.value).toBe('');
  });

  it('輸入「王大明」查詢時應只過濾出 1 筆王大明之紀錄', () => {
    const result = filterRows(sampleRows, '王大明');
    expect(result.length).toBe(1);
    expect(result[0].docNo).toBe('LV-202610-0001');
    expect(result[0].applicant).toContain('王大明');
  });

  it('輸入「TW0102」工號查詢時亦應正確篩選', () => {
    const result = filterRows(sampleRows, 'TW0102');
    expect(result.length).toBe(1);
    expect(result[0].applicant).toBe('王大明 (TW0102)');
  });

  it('輸入單號「LV」或「EX」時應精確過濾相符單據', () => {
    const lvResult = filterRows(sampleRows, 'LV');
    expect(lvResult.length).toBe(1);
    expect(lvResult[0].docNo).toBe('LV-202610-0001');

    const exResult = filterRows(sampleRows, 'EX-202610-0042');
    expect(exResult.length).toBe(1);
    expect(exResult[0].docNo).toBe('EX-202610-0042');
  });

  it('空字串或點擊重設時應回傳全部 4 筆紀錄', () => {
    const allResult = filterRows(sampleRows, '');
    expect(allResult.length).toBe(4);
  });
});

import { describe, it, expect } from 'vitest';
import {
  formatInTimezone,
  parseToUtcInstant,
  isDateOnly,
  TIMEZONES,
} from '../src/utils/time';

describe('時間與時區核心服務 (Time & Timezone Core Service)', () => {
  const utcInstant = '2026-10-23T01:30:00Z'; // UTC 01:30

  it('同一個 UTC instant 在 Asia/Taipei (UTC+8) 與 Asia/Tokyo (UTC+9) 應顯示不同時間', () => {
    const taipeiFormatted = formatInTimezone(utcInstant, TIMEZONES.TAIPEI, 'YYYY-MM-DD HH:mm:ss');
    const tokyoFormatted = formatInTimezone(utcInstant, TIMEZONES.TOKYO, 'YYYY-MM-DD HH:mm:ss');

    // 台北為 09:30:00
    expect(taipeiFormatted).toBe('2026-10-23 09:30:00');
    // 東京為 10:30:00
    expect(tokyoFormatted).toBe('2026-10-23 10:30:00');
  });

  it('在指定時區輸入本地時間應能正確換算回 UTC ISO-8601 instant', () => {
    // 台北時間 2026-10-23 09:30:00 -> UTC 2026-10-23T01:30:00.000Z
    const convertedUtc = parseToUtcInstant('2026-10-23 09:30:00', TIMEZONES.TAIPEI);
    expect(convertedUtc).toBe('2026-10-23T01:30:00.000Z');

    // 東京時間 2026-10-23 10:30:00 -> UTC 2026-10-23T01:30:00.000Z
    const convertedFromTokyo = parseToUtcInstant('2026-10-23 10:30:00', TIMEZONES.TOKYO);
    expect(convertedFromTokyo).toBe('2026-10-23T01:30:00.000Z');
  });

  it('date-only 純日期不應被強制帶上時區偏差或轉換為前一日/後一日', () => {
    const dateStr = '2026-10-23';
    expect(isDateOnly(dateStr)).toBe(true);
    expect(isDateOnly('2026-10-23T09:30:00Z')).toBe(false);
  });
});

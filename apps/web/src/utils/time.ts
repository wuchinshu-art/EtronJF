/**
 * 時間與雙時區工具核心 (Time and Timezone Utility Core)
 * 支援 Asia/Taipei (UTC+8) 與 Asia/Tokyo (UTC+9) 雙時區無縫轉換。
 */

export const TIMEZONES = {
  TAIPEI: 'Asia/Taipei',
  TOKYO: 'Asia/Tokyo',
} as const;

export type SupportedTimezone = (typeof TIMEZONES)[keyof typeof TIMEZONES];

/**
 * 檢查字串是否為 date-only (YYYY-MM-DD)
 */
export function isDateOnly(value: string): boolean {
  return /^\d{4}-\d{2}-\d{2}$/.test(value.trim());
}

/**
 * 將 UTC instant 字串格式化為指定時區的顯示字串
 */
export function formatInTimezone(
  utcIsoString: string,
  timezone: string = TIMEZONES.TAIPEI,
  _format: string = 'YYYY-MM-DD HH:mm:ss'
): string {
  const date = new Date(utcIsoString);
  if (isNaN(date.getTime())) {
    return utcIsoString;
  }

  const formatter = new Intl.DateTimeFormat('en-CA', {
    timeZone: timezone,
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
    hour12: false,
  });

  const parts = formatter.formatToParts(date);
  const partMap: Record<string, string> = {};
  for (const p of parts) {
    partMap[p.type] = p.value;
  }

  const year = partMap.year;
  const month = partMap.month;
  const day = partMap.day;
  const hour = partMap.hour === '24' ? '00' : partMap.hour;
  const minute = partMap.minute;
  const second = partMap.second;

  return `${year}-${month}-${day} ${hour}:${minute}:${second}`;
}

/**
 * 將指定時區的本地時間字串 (YYYY-MM-DD HH:mm:ss) 解析轉換為 UTC ISO-8601 instant
 */
export function parseToUtcInstant(
  localDateTimeStr: string,
  timezone: string = TIMEZONES.TAIPEI
): string {
  const trimmed = localDateTimeStr.trim();
  const match = trimmed.match(/^(\d{4})-(\d{2})-(\d{2})(?:[ T](\d{2}):(\d{2})(?::(\d{2}))?)?$/);
  if (!match) {
    throw new Error(`無效的時間格式: ${localDateTimeStr}`);
  }

  const [_, year, month, day, hour = '00', min = '00', sec = '00'] = match;
  const localAsUtcTimestamp = Date.UTC(+year, +month - 1, +day, +hour, +min, +sec);

  // 取得目標時區在該時間點的實際位移 (Offset)
  const probeDate = new Date(localAsUtcTimestamp);
  const tzFormatter = new Intl.DateTimeFormat('en-US', {
    timeZone: timezone,
    timeZoneName: 'longOffset',
  });
  const tzPart = tzFormatter.formatToParts(probeDate).find(p => p.type === 'timeZoneName')?.value;

  let offsetMinutes = 0;
  if (tzPart && tzPart.startsWith('GMT')) {
    const offsetStr = tzPart.replace('GMT', '');
    if (offsetStr) {
      const sign = offsetStr.startsWith('-') ? -1 : 1;
      const [h, m = '0'] = offsetStr.replace(/^[+-]/, '').split(':');
      offsetMinutes = sign * (+h * 60 + +m);
    }
  } else {
    // 預設時區回退 (Taipei +8, Tokyo +9)
    offsetMinutes = timezone === TIMEZONES.TOKYO ? 540 : 480;
  }

  // 扣除時區 offset 得到真 UTC 時間
  const utcMillis = localAsUtcTimestamp - offsetMinutes * 60 * 1000;
  return new Date(utcMillis).toISOString();
}

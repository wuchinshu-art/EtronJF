import { ref } from 'vue';
import { apiFetch } from './auth';

export interface CompanyItem {
  id: string;
  name: string;
  tax_id: string | null;
  representative_name: string | null;
  registered_address: string | null;
  contact_phone: string | null;
  default_timezone: string;
  default_currency: string;
  is_active: boolean;
  created_at?: string;
  updated_at?: string;
}

// 全域共享公司清單與當前生效公司
export const availableCompanies = ref<CompanyItem[]>([
  {
    id: 'ETJ-TW',
    name: '台灣總部',
    tax_id: null,
    representative_name: null,
    registered_address: null,
    contact_phone: null,
    default_timezone: 'Asia/Taipei',
    default_currency: 'TWD',
    is_active: true,
  },
  {
    id: 'ETJ-JP',
    name: '福岡支社',
    tax_id: null,
    representative_name: null,
    registered_address: null,
    contact_phone: null,
    default_timezone: 'Asia/Tokyo',
    default_currency: 'JPY',
    is_active: true,
  },
]);

export const activeCompanyId = ref<string>(localStorage.getItem('etj_company') || 'ETJ-TW');
export const isCompaniesLoading = ref<boolean>(false);

/**
 * 自後端 /api/v1/hr/companies 動態抓取所有法人公司基本資料
 */
export async function fetchAvailableCompanies(): Promise<CompanyItem[]> {
  isCompaniesLoading.value = true;
  try {
    const res = await apiFetch('/api/v1/hr/companies');
    if (res.ok) {
      const data: CompanyItem[] = await res.json();
      if (Array.isArray(data) && data.length > 0) {
        availableCompanies.value = data;
        // 若當前選擇的公司不存在於後端清單，預設切換為第一家
        if (!data.some((c) => c.id === activeCompanyId.value)) {
          activeCompanyId.value = data[0].id;
          localStorage.setItem('etj_company', data[0].id);
        }
      }
      return data;
    }
  } catch (err) {
    console.error('Failed to load companies:', err);
  } finally {
    isCompaniesLoading.value = false;
  }
  return availableCompanies.value;
}

/**
 * 切換當前生效之所屬公司
 */
export function setActiveCompany(companyId: string) {
  activeCompanyId.value = companyId;
  localStorage.setItem('etj_company', companyId);
}

import { createApp } from 'vue';
import I18NextVue from 'i18next-vue';
import i18next from 'i18next';
import App from './App.vue';
import { initI18n } from './locales/i18n';
import './styles/index.css';

async function bootstrap() {
  await initI18n();

  const app = createApp(App);
  app.use(I18NextVue, { i18next });
  app.mount('#app');
}

bootstrap();

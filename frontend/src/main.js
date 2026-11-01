import { createApp } from 'vue'
import { createPinia } from 'pinia'
import ElementPlus from 'element-plus'
import 'element-plus/dist/index.css'
import './styles/global.css'
import './styles/extra.css'
import './styles/light.css'
import './styles/meteor.css'
import App from './App.vue'
import router from './router'
const app = createApp(App)
app.use(createPinia()).use(router).use(ElementPlus).mount('#app')

import { createRouter, createWebHistory } from 'vue-router'
import NowView from '../views/NowView.vue'
import LogView from '../views/LogView.vue'
import CategoryView from '../views/CategoryView.vue'
import ItemView from '../views/ItemView.vue'
import NoteView from '../views/NoteView.vue'
import TagView from '../views/TagView.vue'
import IndexView from '../views/IndexView.vue'
import AboutView from '../views/AboutView.vue'
import LoginView from '../views/LoginView.vue'
import ManageView from '../views/ManageView.vue'

export default createRouter({
  history: createWebHistory(),
  scrollBehavior: () => ({ top: 0 }),
  routes: [
    { path: '/', redirect: '/now' }, { path: '/now', component: NowView }, { path: '/log', component: LogView },
    { path: '/books', component: CategoryView, props: { code: 'BOOK' } }, { path: '/movies', component: CategoryView, props: { code: 'MOVIE' } },
    { path: '/games', component: CategoryView, props: { code: 'GAME' } }, { path: '/code', component: CategoryView, props: { code: 'CODE' } },
    { path: '/journal', component: CategoryView, props: { code: 'JOURNAL' } }, { path: '/items/:id(\\d+)/:slug?', component: ItemView },
    { path: '/n/:id(\\d+)', component: NoteView }, { path: '/tag/:slug', component: TagView }, { path: '/index', component: IndexView },
    { path: '/about', component: AboutView }, { path: '/manage/login', component: LoginView }, { path: '/manage/:section?', component: ManageView },
  ],
})

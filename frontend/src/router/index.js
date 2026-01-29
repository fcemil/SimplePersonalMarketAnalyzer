import { createRouter, createWebHistory } from 'vue-router'
import Home from '../pages/Home.vue'
import Analyze from '../pages/Analyze.vue'
import Portfolio from '../pages/Portfolio.vue'
import Simulation from '../pages/Simulation.vue'

const routes = [
  { path: '/', name: 'home', component: Home },
  { path: '/analyze/:symbol?', name: 'analyze', component: Analyze },
  { path: '/portfolio', name: 'portfolio', component: Portfolio },
  { path: '/simulate', name: 'simulate', component: Simulation },
]

const router = createRouter({
  history: createWebHistory(),
  routes,
  scrollBehavior() {
    return { top: 0 }
  },
})

export default router

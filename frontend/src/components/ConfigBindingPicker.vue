<template>
  <div class="binding-picker">
    <el-input v-model="search" clearable :placeholder="'搜索' + label + '名称、标识或说明'" />
    <div v-if="missingIds.length" class="missing-bindings">
      <span>以下已绑定配置不存在，请移除：</span>
      <el-tag v-for="id in missingIds" :key="id" type="warning" closable @close="setSelected(id, false)">
        {{ label }} #{{ id }}
      </el-tag>
    </div>
    <div class="binding-table-wrap">
      <table class="binding-table">
        <thead><tr><th scope="col">选择</th><th scope="col">名称 / 标识</th><th scope="col">说明</th><th scope="col">状态</th></tr></thead>
        <tbody>
          <tr v-for="item in filtered" :key="item.id">
            <td><el-checkbox :model-value="selected.has(item.id)"
              :disabled="item.status !== '已启用' && !selected.has(item.id)"
              :aria-label="'选择' + item.name" @change="setSelected(item.id, $event)" /></td>
            <td><strong>{{ item.name }}</strong><small>{{ item.code || '无标识' }}</small></td>
            <td>
              <span>{{ item.description || '暂无说明' }}</span>
              <details v-if="item.content"><summary>查看内容</summary><pre>{{ item.content }}</pre></details>
            </td>
            <td>
              <el-tag size="small" :type="item.status === '已启用' ? 'success' : 'info'">{{ item.status }}</el-tag>
              <small v-if="label === 'Tools'">执行器待接入</small>
            </td>
          </tr>
          <tr v-if="!filtered.length"><td colspan="4" class="binding-empty">{{ items.length ? '没有匹配的配置' : '暂无配置，请先在平台配置中添加' }}</td></tr>
        </tbody>
      </table>
    </div>
    <div class="binding-count">已选择 {{ modelValue.length }} 项<span v-if="inactiveCount">，其中 {{ inactiveCount }} 项未启用，不会生效</span></div>
  </div>
</template>

<script setup>
import { computed, ref } from 'vue'

const props = defineProps({
  label: { type: String, required: true },
  items: { type: Array, default: () => [] },
  modelValue: { type: Array, default: () => [] }
})
const emit = defineEmits(['update:modelValue'])
const search = ref('')
const selected = computed(() => new Set(props.modelValue))
const filtered = computed(() => {
  const term = search.value.trim().toLowerCase()
  return props.items.filter((item) => [item.name, item.code, item.description].some((value) => (value || '').toLowerCase().includes(term)))
})
const missingIds = computed(() => props.modelValue.filter((id) => !props.items.some((item) => item.id === id)))
const inactiveCount = computed(() => props.items.filter((item) => selected.value.has(item.id) && item.status !== '已启用').length)
function setSelected(id, enabled) {
  emit('update:modelValue', enabled ? [...props.modelValue.filter((value) => value !== id), id] : props.modelValue.filter((value) => value !== id))
}
</script>

<style scoped>
.binding-picker { width: 100%; }
.binding-table-wrap { max-height: 260px; overflow: auto; margin-top: 8px; border: 1px solid var(--line); border-radius: 8px; }
.binding-table { width: 100%; border-collapse: collapse; font-size: 12px; line-height: 1.5; }
.binding-table th, .binding-table td { padding: 8px 10px; border-bottom: 1px solid var(--line); text-align: left; vertical-align: top; }
.binding-table th { position: sticky; top: 0; z-index: 1; background: var(--panel2); white-space: nowrap; }
.binding-table tr:last-child td { border-bottom: 0; }
.binding-table small { display: block; color: var(--muted); overflow-wrap: anywhere; }
.binding-table details { margin-top: 4px; }
.binding-table summary { color: var(--cyan); cursor: pointer; }
.binding-table pre { max-height: 160px; overflow: auto; white-space: pre-wrap; overflow-wrap: anywhere; font: inherit; color: var(--muted); }
.binding-empty { text-align: center !important; color: var(--muted); }
.binding-count, .missing-bindings { margin-top: 6px; color: var(--muted); font-size: 12px; }
.missing-bindings { display: flex; align-items: center; flex-wrap: wrap; gap: 5px; }
</style>

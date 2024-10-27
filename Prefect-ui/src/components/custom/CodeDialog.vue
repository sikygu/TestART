<template>
  <el-dialog v-model="dialogTableVisible" title="测试代码" append-to-body style="top: -10%">
    <el-scrollbar ref="scrollbarRef" always>
      <Markdown :content="props.content"></Markdown>
    </el-scrollbar>
  </el-dialog>

</template>
<script setup>

import {onMounted, ref, watch} from "vue";
import Markdown from "@/components/custom/Markdown.vue";

const props = defineProps({
  content: {
    type: String,
    default: () => {
      return "**no content**"
    }
  },
  onClick: {
    type: Number,
    default: 0
  }
});


const scrollbarRef = ref(null);
const dialogTableVisible = ref(false);
watch(() => props.onClick, (val) => {
  dialogTableVisible.value = true;
  setTimeout(() => {
    scrollbarRef.value?.setScrollTop(0);
  }, 100);
})
</script>


<style scoped>

</style>
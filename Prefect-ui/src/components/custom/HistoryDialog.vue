<template>
  <el-dialog v-model="dialogTableVisible" title="LLM交互历史" append-to-body style="top: -10%">
    <el-collapse v-model="activeName" accordion>
      <el-collapse-item v-for="(item,i) in props.data" :title="item.title" :name="i">
        <el-scrollbar ref="scrollbarRef" always :native="true">
          <Markdown v-if="activeName === i" :content="item.content" style="height: 600px"></Markdown>
        </el-scrollbar>
      </el-collapse-item>
    </el-collapse>
  </el-dialog>
</template>
<script setup>

import {onMounted, ref, watch} from "vue";
import Markdown from "@/components/custom/Markdown.vue";

const props = defineProps({
  data: {
    type: Array,
    default: () => {
      return [
        {title: "temp", content: "temp"}
      ]
    }
  },
  onClick: {
    type: Number,
    default: 0
  }
});

const activeName = ref('1');


const scrollbarRef = ref(null);
const dialogTableVisible = ref(false);
watch(() => props.onClick, (val) => {
  dialogTableVisible.value = true;
})
</script>


<style scoped>

</style>

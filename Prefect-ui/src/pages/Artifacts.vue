<template>
  <p-layout-default class="artifacts">
    <template #header>
      <div style="font-size: 1.25em;font-weight: bold">Results</div>
    </template>
    <BatchAttemptStatusTable :data="data" v-loading="loading"></BatchAttemptStatusTable>
    <FlowRunRequestDialog :form="flowRunRequestDialogForm" :onClick="flowRunRequestDialogClick"></FlowRunRequestDialog>
    <HistoryDialog :data="historyDialogArray" :onClick="historyDialogClick"></HistoryDialog>
    <CodeDialog :content="codeDialogContent" :onClick="codeDialogOnClick"></CodeDialog>

  </p-layout-default>



</template>

<script setup>
import {usePageTitle} from '@/compositions/usePageTitle'
import {ElMessage} from "element-plus";
import axios from 'axios'
import BatchAttemptStatusTable from "@/components/custom/BatchAttemptStatusTable.vue";
import {reactive, ref, toRaw} from "vue";
import FlowRunRequestDialog from "@/components/custom/FlowRunRequestDialog.vue";
import HistoryDialog from "@/components/custom/HistoryDialog.vue";
import {provide} from 'vue'
import CodeDialog from "@/components/custom/CodeDialog.vue";

usePageTitle('Results')

const loading = ref(true);
let data = ref([]);
axios.get("http://localhost:25734/")
    .then((res) => {
      data.value = res.data;
    })
    .catch(err => {
      ElMessage({
        message: "请求未响应，请查看后端25734端口服务是否开启",
        type: 'error'
      })
    })
    .finally(() => {
      loading.value = false;
    });
const historyDialogArray = ref([]);
const historyDialogClick = ref(0);
const flowRunRequestDialogClick = ref(0);
const flowRunRequestDialogForm = ref({});
const codeDialogContent = ref("");
const codeDialogOnClick = ref(0);
const showFlowRunRequestDialog = (form) => {
  form = toRaw(form);
  console.log("showFlowRunRequestDialog", toRaw(form))
  flowRunRequestDialogClick.value = new Date().getTime();
  flowRunRequestDialogForm.value = form;
};
const showHistoryDialog = (content) => {
  content = toRaw(content);
  console.log("showHistoryDialog", content)
  historyDialogArray.value = content;
  historyDialogClick.value = new Date().getTime();
};
const showCodeDialog = (content) => {
  content = toRaw(content);
  console.log("showCodeDialog", content)
  codeDialogContent.value = content;
  codeDialogOnClick.value = new Date().getTime();
};
provide('showFlowRunRequestDialog', showFlowRunRequestDialog);
provide('showHistoryDialog', showHistoryDialog);
provide('showCodeDialog', showCodeDialog);
</script>

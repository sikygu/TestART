<template>
  <el-table
      ref="table"
      :data="props.data"
      highlight-current-row
      style="width: 100%;">
    <el-table-column
        property="doc_id"
        min-width="50">
    </el-table-column>
    <el-table-column
        property="dataset"
        label="数据集"
        min-width="120">
    </el-table-column>
    <el-table-column
        property="num"
        label="数量"
        min-width="80">
    </el-table-column>
    <el-table-column
        property="no"
        label="数据编号"
        min-width="80">
    </el-table-column>
    <el-table-column
        label="执行结果(FAIL/SE/CE/RE/PASS)"
        min-width="200">
      <template #default="scope">
        <div style="display: flex">
          <el-tag disable-transitions class="ml-2" type="danger">{{ scope.row.status.fail }}</el-tag>
          <el-tag disable-transitions class="ml-2" type="warning">{{ scope.row.status.syntax_error }}</el-tag>
          <el-tag disable-transitions class="ml-2" type="warning">{{ scope.row.status.compile_error }}</el-tag>
          <el-tag disable-transitions class="ml-2" type="warning">{{ scope.row.status.runtime_error }}</el-tag>
          <el-tag disable-transitions class="ml-2" type="success">{{ scope.row.status.pass }}</el-tag>
        </div>
      </template>
    </el-table-column>
    <el-table-column
        prop="start_time"
        label="开始时间"
        min-width="170">
    </el-table-column>
    <el-table-column
        prop="end_time"
        label="结束时间"
        min-width="170">
    </el-table-column>
    <el-table-column
        prop="duration"
        label="持续时间"
        min-width="120">
    </el-table-column>
    <el-table-column
        prop="mode"
        label="模式"
        min-width="100">
    </el-table-column>
    <el-table-column
        label="详细查看"
        min-width="200">
      <template #default="scope">
        <el-button type="primary" size="small" @click="openDialog(scope.row)">运行参数</el-button>
      </template>
    </el-table-column>
    <el-table-column type="expand">
      <template #default="scope">
        <AttemptStatusTable :data="scope.row.attempts" :doc_id="scope.row.doc_id"></AttemptStatusTable>
      </template>
    </el-table-column>
  </el-table>



</template>

<script setup>

import AttemptStatusTable from "@/components/custom/AttemptStatusTable.vue";
import {ref, inject} from "vue";

const showFlowRunRequestDialog = inject('showFlowRunRequestDialog');
const showHistoryDialog = inject('showHistoryDialog');
const props = defineProps({
  data: {
    type: Array,
    default: () => {
      return []
    }
  }
})

const openDialog = (row) => {
  showFlowRunRequestDialog(row.flow_run_request);
};


</script>

<style scoped>

</style>

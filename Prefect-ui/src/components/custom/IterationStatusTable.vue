<template>
  <el-table
      ref="table"
      :data="props.data"
      highlight-current-row
      default-expand-all
      style="width: 100%;">
    <el-table-column
        type="index"
        label="迭代 No."
        width="80">
    </el-table-column>
    <el-table-column
        label="&nbsp;&nbsp;备注"
        min-width="200">
      <template #default="scope">
        <el-tag disable-transitions v-show="scope.$index === props.index" class="ml-2" type="success">最终结果</el-tag>
      </template>
    </el-table-column>
    <el-table-column
        prop="retry"
        label="重试次数"
        min-width="90">
    </el-table-column>
    <el-table-column
        prop="start_time"
        label="开始时间"
        min-width="90">
    </el-table-column>
    <el-table-column
        prop="duration"
        label="持续时间"
        min-width="120">
    </el-table-column>
    <el-table-column
        label="&nbsp;&nbsp;状态"
        width="140">
      <template #default="scope">
        <div style="display: flex">
          <el-tag disable-transitions v-show="scope.row.type === 'PASS'" class="ml-2" type="success">{{ scope.row.type }}</el-tag>
          <el-tag disable-transitions v-show="scope.row.type === 'SYNTAX_ERROR'" class="ml-2" type="warning">{{ scope.row.type }}</el-tag>
          <el-tag disable-transitions v-show="scope.row.type === 'COMPILE_ERROR'" class="ml-2" type="warning">{{ scope.row.type }}</el-tag>
          <el-tag disable-transitions v-show="scope.row.type === 'RUNTIME_ERROR'" class="ml-2" type="warning">{{ scope.row.type }}</el-tag>
          <el-tag disable-transitions v-show="scope.row.type === 'FAIL'" class="ml-2" type="danger">{{ scope.row.type }}</el-tag>
        </div>
      </template>
    </el-table-column>
    <el-table-column
        prop="exception"
        label="错误代码"
        :show-overflow-tooltip="true"
        min-width="120">
    </el-table-column>
    <el-table-column
        prop="cover_value"
        label="覆盖统计"
        min-width="120">
    </el-table-column>
    <el-table-column
        prop="value"
        label="覆盖率"
        min-width="80">
    </el-table-column>
    <el-table-column
        label="详细查看"
        width="100">
      <template #default="scope">
        <el-button type="primary" size="small" @click="openHistoryDialog(scope.row.llm_records)">LLM记录</el-button>
      </template>
    </el-table-column>
    <el-table-column type="expand">
      <template #default="scope">
        <TestStatusTable :data="scope.row.sub_test_status" :index="scope.row.index"></TestStatusTable>
      </template>
    </el-table-column>
  </el-table>


</template>

<script setup>
import {inject, ref, watch} from "vue";
import TestStatusTable from "@/components/custom/TestStatusTable.vue";
const showHistoryDialog = inject('showHistoryDialog');
const props = defineProps({
  data: {
    type: Array,
    default: () => []
  },
  index: {
    type: Number,
    default: 0
  }
});

const openHistoryDialog = (content) => {
  showHistoryDialog(content);
};
</script>


<style scoped>

</style>

<template>
  <el-table
      ref="table"
      :data="props.data"
      highlight-current-row
      style="width: 97%; left: 3%;">
    <el-table-column
        type="index"
        label="执行 No."
        width="80">
    </el-table-column>
    <el-table-column prop="branch" label="分支数（覆盖/总计/比例）" width="200"></el-table-column>
    <el-table-column prop="line" label="行数（覆盖/总计/比例）" width="200"></el-table-column>
    <el-table-column prop="tests" label="Tests" min-width="30"></el-table-column>
    <el-table-column prop="failures" label="Failures" min-width="40"></el-table-column>
    <el-table-column prop="errors" label="Errors" min-width="30"></el-table-column>
    <el-table-column prop="skipped" label="Skipped" min-width="40"></el-table-column>
    <el-table-column prop="passed" label="Passed" min-width="40"></el-table-column>
    <el-table-column label="Type" min-width="50">
      <template #default="scope">
        <div style="display: flex">
          <el-tag disable-transitions v-show="scope.row.type === '成功'" class="ml-2" type="success">{{ scope.row.type }}</el-tag>
          <el-tag disable-transitions v-show="scope.row.type === '修复成功'" class="ml-2" type="success">{{ scope.row.type }}</el-tag>
          <el-tag disable-transitions v-show="scope.row.type === '修复失败'" class="ml-2" type="danger">{{ scope.row.type }}</el-tag>
          <el-tag disable-transitions v-show="scope.row.type === '失败'" class="ml-2" type="danger">{{ scope.row.type }}</el-tag>
        </div>
      </template>

    </el-table-column>
    <el-table-column prop="retry" label="Retry No." min-width="40"></el-table-column>
    <el-table-column
        label="详细查看"
        min-width="100">
      <template #default="scope">
        <el-button type="primary" size="small" @click="openCodeDialog(scope.row.code)">测试代码</el-button>
        <el-button type="primary" size="small" @click="openCodeDialog(scope.row.code_diff)" >修复对比</el-button>
      </template>
    </el-table-column>
  </el-table>


</template>

<script setup>

import CodeDialog from "@/components/custom/CodeDialog.vue";
import {ref, inject} from "vue";

const props = defineProps({
  data: {
    type: Array,
    default: () => {
      return []
    }
  },
  index: {
    type: Number,
    default: 0
  }
});
const showCodeDialog = inject('showCodeDialog');
const openCodeDialog = (val) => {
  showCodeDialog(val);

};



</script>

<style scoped>

</style>

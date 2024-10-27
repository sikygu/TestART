<template>
  <el-table
      ref="table"
      :data="pagedData"
      highlight-current-row
      @sort-change="handleSortChange"
      style="width: 97%; left: 3%;">
    <el-table-column
        prop="idx"
        label="id"
        min-width="60">
    </el-table-column>
    <el-table-column
        label="类名"
        show-overflow-tooltip
        min-width="120">
      <template #default="scope">
        <el-link :href="scope.row.link">{{ scope.row.clazz }}</el-link>
      </template>
    </el-table-column>
    <el-table-column
        property="method"
        label="方法签名"
        :show-overflow-tooltip="true"
        min-width="300">
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
        prop="type"
        label="&nbsp;&nbsp;状态"
        sortable="custom"
        width="140">
      <template #default="scope">
        <div style="display: flex">
          <el-tag disable-transitions v-show="scope.row.type === 'PASS'" class="ml-2" type="success">{{
              scope.row.type
            }}
          </el-tag>
          <el-tag disable-transitions v-show="scope.row.type === 'SYNTAX_ERROR'" class="ml-2" type="warning">
            {{ scope.row.type }}
          </el-tag>
          <el-tag disable-transitions v-show="scope.row.type === 'COMPILE_ERROR'" class="ml-2" type="warning">
            {{ scope.row.type }}
          </el-tag>
          <el-tag disable-transitions v-show="scope.row.type === 'RUNTIME_ERROR'" class="ml-2" type="warning">
            {{ scope.row.type }}
          </el-tag>
          <el-tag disable-transitions v-show="scope.row.type === 'FAIL'" class="ml-2" type="danger">{{
              scope.row.type
            }}
          </el-tag>
        </div>
      </template>
    </el-table-column>
    <el-table-column
        prop="exceptions"
        label="错误代码"
        sortable="custom"
        :show-overflow-tooltip="true"
        min-width="120">
    </el-table-column>
    <el-table-column
        prop="num"
        label="迭代次数"
        sortable="custom"
        min-width="100">
    </el-table-column>
    <el-table-column
        prop="cover_value"
        label="覆盖统计"
        min-width="120">
    </el-table-column>
    <el-table-column
        prop="value"
        label="覆盖率"
        sortable="custom"
        min-width="120">
    </el-table-column>
    <el-table-column
        label="详细查看"
        min-width="200">
      <template #default="scope">
        <el-button type="primary" size="small" @click="openDrawer(scope.row)">迭代过程</el-button>
      </template>
    </el-table-column>
  </el-table>
  <div style="display: flex; justify-content: center; margin-top: 5px;">
    <el-pagination
        @size-change="handleSizeChange"
        @current-change="handleCurrentChange"
        :current-page="currentPage"
        :page-size="pageSize"
        background
        layout="total, prev, pager, next, jumper"
        :total="props.data.length">
    </el-pagination>
  </div>
  <el-drawer v-model="drawer"  title="I am the title" :with-header="false" size="80%" direction="ltr" append-to-body>
    <IterationStatusTable v-loading="loading" :data="iterationStatus" :index="iterationStatusIndex"></IterationStatusTable>
  </el-drawer>


</template>

<script setup>
import {computed, ref} from "vue";
import IterationStatusTable from "@/components/custom/IterationStatusTable.vue";
import axios from "axios";
import {ElMessage} from "element-plus";

const props = defineProps({
  data: {
    type: Array,
    default: () => {
      return []
    }
  },
  doc_id: {
    type: Number,
    default: 0
  }
});

const currentPage = ref(1);
const pageSize = ref(10);

const pagedData = computed(() => {
  let data = JSON.parse(JSON.stringify(props.data));
  data.sort((a,b) => {
    let item = currentSort.value;
    if(a[item.prop] > b[item.prop]) {
      return item.order === 'ascending' ? 1 : -1;
    } else if(a[item.prop] < b[item.prop]) {
      return item.order === 'ascending' ? -1 : 1;
    }
    return 0;
  })
  const start = (currentPage.value - 1) * pageSize.value;
  const end = start + pageSize.value;
  return data.slice(start, end);

});

const handleSizeChange = (val) => {
  pageSize.value = val;
  currentPage.value = 1;
};

const currentSort = ref({});
const handleCurrentChange = (val) => {
  console.log("current-page", val);
  currentPage.value = val;
};

const handleSortChange = (val) => {
  currentSort.value = val;
};

const drawer = ref(false);
const iterationStatus = ref([]);
const iterationStatusIndex = ref(0);
const loading = ref(false);
const openDrawer = (row) => {
  drawer.value = true;
  loading.value = true;
  axios.get("http://localhost:25734/iteration_status?doc_id=" + props.doc_id + "&aid=" + row.idx)
      .then((res) => {
        iterationStatus.value = res.data;
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
  iterationStatusIndex.value = row.index;
};


</script>

<style scoped>

</style>

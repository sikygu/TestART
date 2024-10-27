<template>
  <el-dialog v-model="dialogTableVisible" title="运行参数" append-to-body style="top: -10%">
    <el-form :model="props.form" label-width="150px">
      <el-form-item label="Mode">
        <el-select v-model="form.mode" placeholder="Select mode">
          <el-option
              v-for="item in coverageModes"
              :key="item.value"
              :label="item.label"
              :value="item.value"
          ></el-option>
        </el-select>
      </el-form-item>

      <!-- Assuming LLMConfig is a nested form -->
      <el-form-item label="LLM Model">
        <el-input v-model="form.llm_config.model"></el-input>
      </el-form-item>

      <el-form-item label="API Base">
        <el-input v-model="form.llm_config.api_base"></el-input>
      </el-form-item>

      <el-form-item label="Temperature">
        <el-input-number v-model="form.llm_config.temperature"></el-input-number>
      </el-form-item>

      <el-form-item label="Seed">
        <el-input-number v-model="form.llm_config.seed"></el-input-number>
      </el-form-item>

      <el-form-item label="Frequency Penalty">
        <el-input-number v-model="form.llm_config.frequency_penalty"></el-input-number>
      </el-form-item>

      <el-form-item label="Timeout(s)">
        <el-input-number v-model="form.llm_config.request_timeout"></el-input-number>
      </el-form-item>

      <el-form-item label="Max Retry">
        <el-input-number v-model="form.max_retry"></el-input-number>
      </el-form-item>

      <el-form-item label="Max Iteration">
        <el-input-number v-model="form.max_iteration"></el-input-number>
      </el-form-item>

      <el-form-item label="Max Fix">
        <el-input-number v-model="form.max_fix"></el-input-number>
      </el-form-item>

      <el-form-item label="Auto Fix">
        <el-switch v-model="form.auto_fix"></el-switch>
      </el-form-item>

      <el-form-item label="Cache Key">
        <el-input v-model="form.cache_key" :disabled="true"></el-input>
      </el-form-item>

      <el-form-item label="Dataset Name">
        <el-input v-model="form.dataset_name"></el-input>
      </el-form-item>

      <el-form-item label="Dataset Size">
        <el-input-number v-model="form.dataset_size"></el-input-number>
      </el-form-item>

      <el-form-item label="Dataset Start Index">
        <el-input-number v-model="form.dataset_start_index"></el-input-number>
      </el-form-item>

    </el-form>
  </el-dialog>
</template>
<script setup >
import {ref, watch} from "vue";
const coverageModes = [
  {label: 'Branch Coverage', value: 'BRANCH_COVERAGE'},
  {label: 'Line Coverage', value: 'LINE_COVERAGE'},
];
const props = defineProps({
  form: {
    type: Object,
    default: () => {
      return {}
    }
  },
  onClick: {
    type: Number,
    default: 0
  }
})
let dialogTableVisible = ref(false);
watch(() => props.onClick, (val) => {
  dialogTableVisible.value = true;
})
</script>



<style scoped>

</style>

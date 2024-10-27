<template>
  <p-layout-default class="artifacts">
    <template #header>
      <div style="font-size: 1.25em;font-weight: bold">Dataset</div>
    </template>

    <el-tabs v-model="activeTab">
      <el-tab-pane label="Upload" name="upload">
        <div class="upload-container">
          <el-upload
            ref="upload"
            action="http://localhost:25734/upload"
            :on-success="handleSuccess"
            :on-error="handleError"
            :limit="1"
            :on-exceed="handleExceed"
            :auto-upload="false"
          >
            <template #trigger>
              <el-button type="primary">select file</el-button>
            </template>
            <el-button class="ml-3" type="success" @click="submitUpload">
              upload to server
            </el-button>
            <template #tip>
              <div class="el-upload__tip">
                .zip files with a size less than 50MB.
              </div>
            </template>
            <div slot="tip" class="el-upload__tip"></div>
          </el-upload>
        </div>
      </el-tab-pane>
      <el-tab-pane label="Dataset List" name="list">
        <!-- Dataset list goes here -->
      </el-tab-pane>
    </el-tabs>

  </p-layout-default>
</template>

<script setup>
import {usePageTitle} from '@/compositions/usePageTitle'
import {ElMessage, ElTabs, ElTabPane, ElUpload, ElButton} from "element-plus";
import axios from 'axios'
import {ref} from "vue";
import { genFileId } from 'element-plus'
usePageTitle('Datasets')

let activeTab = 'upload'

const handleSuccess = (response, file, fileList) => {
  let msg = response.msg;
  if (msg) {
    ElMessage.error("文件上传失败：" + msg)
    return
  }
  ElMessage.success('文件上传成功');
};

const handleError = (err, file, fileList) => {
  ElMessage.error('文件上传失败')
}
const upload = ref(null);
const handleExceed = (files) => {
  upload.value?.clearFiles()
  const file = files[0]
  file.uid = genFileId()
  upload.value?.handleStart(file)
}
const submitUpload = () => {
  upload.value?.submit()
}
</script>

<style scoped>
.upload-container {
  display: flex;
  justify-content: center;
  align-items: center;
  height: 100%;
}
</style>

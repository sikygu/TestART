<template>
  <div id="viewer" ref="viewerRef" style="max-height: 700px"></div>
</template>

<script setup>

import {onMounted, ref, watch} from "vue";
import 'cherry-markdown/dist/cherry-markdown.css';
import Cherry from 'cherry-markdown';


let cherryInstance = null;
const viewerRef = ref(null);
onMounted(() => {
  cherryInstance = new Cherry({
    id: 'viewer',
    value: '** no content **',
    editor: {
      defaultModel: 'previewOnly',
    },

  });
  cherryInstance.setMarkdown(first, false);
});

const props = defineProps({
  content: {
    type: String,
    default: () => {
      return "**no content**"
    }
  }
})
let first = "** no content **"
watch(() => props.content, (val) => {
      if (!viewerRef.value) {
        first = val;
        return;
      }
      cherryInstance.setMarkdown(val, false);
    }, {
      immediate: true
    }
);


</script>

<style scoped>

</style>

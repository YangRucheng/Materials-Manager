<template>
  <n-result status="404" title="页面不存在" description="请检查访问地址"
    ><template #footer
      ><n-button @click="$router.push('/dashboard')">返回工作台</n-button></template
    ></n-result
  >
</template>

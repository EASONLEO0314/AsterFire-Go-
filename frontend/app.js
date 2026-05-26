/* ============================================================
   AI 智能简历分析系统 — Vue 3 应用逻辑
   ============================================================ */

const API_BASE = window.API_BASE || 'http://localhost:5001'

/* ---- Score Ring 组件 ---- */
const ScoreRing = {
  name: 'ScoreRing',
  props: { label: String, value: { type: Number, default: 0 }, color: String },
  template: `
    <div class="ring-container">
      <svg viewBox="0 0 120 120" class="ring-svg">
        <circle cx="60" cy="60" r="50" fill="none" stroke="#e5e7eb" stroke-width="10"/>
        <circle cx="60" cy="60" r="50" fill="none" :stroke="color" stroke-width="10"
          stroke-linecap="round" :stroke-dasharray="dasharray" :stroke-dashoffset="dashoffset"
          class="ring-arc" transform="rotate(-90 60 60)"/>
        <text x="60" y="56" text-anchor="middle" class="ring-value">{{ value }}</text>
        <text x="60" y="74" text-anchor="middle" class="ring-unit">分</text>
      </svg>
      <span class="ring-label">{{ label }}</span>
    </div>
  `,
  computed: {
    circumference() { return 2 * Math.PI * 50 },
    dasharray() { return this.circumference },
    dashoffset() { return this.circumference * (1 - this.value / 100) },
  },
}

/* ---- Root App ---- */
const { createApp } = Vue
const app = createApp({
  data() {
    return {
      // workflow state
      step: 'upload',      // upload | parsed | extracting | extracted | matching | matched
      loading: false,
      error: null,

      // upload
      isDragover: false,
      resumeId: '',
      fileInfo: { fileName: '', pages: 0 },
      cleanedText: '',

      // extract
      extractedInfo: null,

      // match
      jobDescription: '',
      matchResult: null,

      // api
      apiOnline: false,
    }
  },

  created() {
    this.checkApiStatus()
  },

  methods: {
    /* ---- API helpers ---- */
    async api(path, opts = {}) {
      const url = API_BASE + path
      const res = await fetch(url, {
        headers: { ...(opts.headers || {}) },
        ...opts,
        headers: opts.body instanceof FormData
          ? opts.headers || {}
          : { 'Content-Type': 'application/json', ...(opts.headers || {}) },
      })
      if (!res.ok) throw new Error(`HTTP ${res.status}`)
      const json = await res.json()
      if (json.code !== 0) throw new Error(json.msg || '未知错误')
      return json.data
    },

    async checkApiStatus() {
      try {
        const res = await fetch(API_BASE + '/api/cache/stats')
        if (res.ok) { this.apiOnline = true; return }
      } catch (_) { /* offline */ }
      this.apiOnline = false
    },

    /* ---- Upload ---- */
    triggerFileInput() { this.$refs.fileInput.click() },
    handleFileSelect(e) { const f = e.target.files[0]; if (f) this.uploadFile(f) },
    handleDrop(e) {
      this.isDragover = false
      const f = e.dataTransfer.files[0]
      if (f) this.uploadFile(f)
    },

    async uploadFile(file) {
      // 客户端预校验
      if (!file.name.toLowerCase().endsWith('.pdf')) return this.showError('仅支持 PDF 格式')
      if (file.size > 10 * 1024 * 1024) return this.showError('文件过大，请上传 ≤10MB 的 PDF')

      this.loading = true
      this.error = null
      try {
        const fd = new FormData()
        fd.append('file', file)
        const data = await this.api('/api/resume/upload', { method: 'POST', body: fd })
        this.resumeId = data.resumeId
        this.fileInfo = { fileName: data.fileName, pages: data.pages }
        this.cleanedText = data.cleanedText
        this.step = 'parsed'
      } catch (e) {
        this.showError('上传失败: ' + e.message)
      } finally {
        this.loading = false
      }
    },

    /* ---- Extract ---- */
    async doExtract() {
      this.loading = true
      this.error = null
      this.step = 'extracting'
      try {
        const data = await this.api('/api/resume/extract', {
          method: 'POST',
          body: JSON.stringify({ resumeId: this.resumeId }),
        })
        this.extractedInfo = data
        this.step = 'extracted'
      } catch (e) {
        this.showError('AI 提取失败: ' + e.message)
        this.step = 'parsed'
      } finally {
        this.loading = false
      }
    },

    /* ---- Match ---- */
    async doMatch() {
      if (!this.jobDescription.trim()) return this.showError('请输入岗位描述')
      this.loading = true
      this.error = null
      this.step = 'matching'
      try {
        const data = await this.api('/api/match', {
          method: 'POST',
          body: JSON.stringify({ resumeId: this.resumeId, jobDescription: this.jobDescription }),
        })
        this.matchResult = data
        this.step = 'matched'
      } catch (e) {
        this.showError('匹配评分失败: ' + e.message)
        this.step = 'extracted'
      } finally {
        this.loading = false
      }
    },

    showError(msg) { this.error = msg; setTimeout(() => { this.error = null }, 8000) },
  },
})

app.component('score-ring', ScoreRing)
app.mount('#app')

/* ============================================================
   AI 智能简历分析系统 — Vue 3 应用逻辑
   ============================================================ */

const API_BASE = window.API_BASE || 'http://39.105.105.248'

/* ---- Score Ring 组件 ---- */
const ScoreRing = {
  name: 'ScoreRing',
  props: {
    label: String,
    value: { type: Number, default: 0 },
    color: String,
    primary: { type: Boolean, default: false },
  },
  template: `
    <div class="ring-container" :class="{ primary }">
      <svg viewBox="0 0 120 120" class="ring-svg">
        <circle cx="60" cy="60" r="50" fill="none" stroke="var(--border-light)" stroke-width="9"/>
        <circle cx="60" cy="60" r="50" fill="none" :stroke="color" stroke-width="9"
          stroke-linecap="round" :stroke-dasharray="dasharray" :stroke-dashoffset="dashoffset"
          class="ring-arc" transform="rotate(-90 60 60)"/>
        <text x="60" y="56" text-anchor="middle" class="ring-value">{{ displayValue }}</text>
        <text x="60" y="74" text-anchor="middle" class="ring-unit">分</text>
      </svg>
      <span class="ring-label">{{ label }}</span>
    </div>
  `,
  data() {
    return { displayValue: 0 }
  },
  computed: {
    circumference() { return 2 * Math.PI * 50 },
    dasharray() { return this.circumference },
    dashoffset() { return this.circumference * (1 - this.displayValue / 100) },
  },
  watch: {
    value: {
      handler(newVal) { this.animateValue(newVal) },
      immediate: true,
    },
  },
  methods: {
    animateValue(target) {
      const start = this.displayValue
      const diff = target - start
      if (diff === 0) return
      const duration = 1000
      const startTime = performance.now()
      const step = (now) => {
        const elapsed = now - startTime
        const progress = Math.min(elapsed / duration, 1)
        // ease-out-quart
        const eased = 1 - Math.pow(1 - progress, 4)
        this.displayValue = Math.round(start + diff * eased)
        if (progress < 1) requestAnimationFrame(step)
      }
      requestAnimationFrame(step)
    },
  },
}

/* ---- Extraction status messages ---- */
const EXTRACT_MESSAGES = [
  '正在解析简历结构',
  '识别关键字段信息',
  '提取个人基本信息',
  '分析教育背景与学历',
  '识别工作经历与项目',
  '提取技术栈与技能标签',
  '整理结构化数据',
]

/* ---- Root App ---- */
const { createApp } = Vue
const app = createApp({
  data() {
    return {
      // workflow state
      step: 'upload',
      loading: false,
      error: null,

      // upload
      isDragover: false,
      resumeId: '',
      fileInfo: { fileName: '', pages: 0 },
      cleanedText: '',

      // extract
      extractedInfo: null,
      extractStatusText: '',
      _extractMsgIdx: 0,
      _extractMsgTimer: null,

      // match
      jobDescription: '',
      matchResult: null,
      displayScores: { total: 0, skill: 0, experience: 0, education: 0 },

      // api
      apiOnline: false,
      _errorTimer: null,
    }
  },

  created() {
    this.checkApiStatus()
    this._healthTimer = setInterval(() => this.checkApiStatus(), 30000)
  },

  beforeUnmount() {
    clearInterval(this._healthTimer)
    clearTimeout(this._errorTimer)
    clearInterval(this._extractMsgTimer)
  },

  methods: {
    /* ---- API helpers ---- */
    async api(path, opts = {}) {
      const url = API_BASE + path
      const isFormData = opts.body instanceof FormData
      const res = await fetch(url, {
        ...opts,
        headers: isFormData
          ? (opts.headers || {})
          : { 'Content-Type': 'application/json', ...(opts.headers || {}) },
      })
      if (!res.ok) throw new Error(`HTTP ${res.status}`)
      const json = await res.json()
      if (json.code !== 0) throw new Error(json.msg || '未知错误')
      return json.data
    },

    async checkApiStatus() {
      try {
        const res = await fetch(API_BASE + '/api/health')
        if (res.ok) { this.apiOnline = true; return }
      } catch (_) { /* offline */ }
      this.apiOnline = false
    },

    /* ---- Drop zone mouse tracking ---- */
    onDropZoneMouseMove(e) {
      const zone = e.currentTarget
      const rect = zone.getBoundingClientRect()
      const x = ((e.clientX - rect.left) / rect.width) * 100
      const y = ((e.clientY - rect.top) / rect.height) * 100
      zone.style.setProperty('--mx', x + '%')
      zone.style.setProperty('--my', y + '%')
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
    _startExtractAnimation() {
      this._extractMsgIdx = 0
      this.extractStatusText = EXTRACT_MESSAGES[0]
      this._extractMsgTimer = setInterval(() => {
        this._extractMsgIdx++
        if (this._extractMsgIdx < EXTRACT_MESSAGES.length) {
          this.extractStatusText = EXTRACT_MESSAGES[this._extractMsgIdx]
        }
      }, 600)
    },

    _stopExtractAnimation() {
      clearInterval(this._extractMsgTimer)
      this._extractMsgTimer = null
    },

    async doExtract() {
      this.loading = true
      this.error = null
      this.step = 'extracting'
      this._startExtractAnimation()
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
        this._stopExtractAnimation()
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
        // Animate scores counting up
        this.$nextTick(() => {
          this.displayScores = {
            total: data.totalScore || 0,
            skill: data.skillMatch || 0,
            experience: data.experienceMatch || 0,
            education: data.educationMatch || 0,
          }
        })
      } catch (e) {
        this.showError('匹配评分失败: ' + e.message)
        this.step = 'extracted'
      } finally {
        this.loading = false
      }
    },

    resetMatch() {
      this.step = 'extracted'
      this.matchResult = null
      this.jobDescription = ''
      this.displayScores = { total: 0, skill: 0, experience: 0, education: 0 }
    },

    showError(msg) {
      this.error = msg
      clearTimeout(this._errorTimer)
      this._errorTimer = setTimeout(() => { this.error = null }, 8000)
    },
  },
})

app.component('score-ring', ScoreRing)
app.mount('#app')

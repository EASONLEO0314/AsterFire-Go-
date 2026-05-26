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
    <div :class="primary ? 'w-[140px]' : 'w-[90px]'" class="text-center">
      <svg :class="primary ? 'w-[140px] h-[140px]' : 'w-[90px] h-[90px]'" class="block mx-auto mb-2" viewBox="0 0 120 120" style="filter: drop-shadow(0 2px 8px rgba(0,0,0,0.3));">
        <circle cx="60" cy="60" r="50" fill="none" stroke="rgba(255,255,255,0.06)" stroke-width="9"/>
        <circle cx="60" cy="60" r="50" fill="none" :stroke="color" stroke-width="9"
          stroke-linecap="round" :stroke-dasharray="dasharray" :stroke-dashoffset="dashoffset"
          transform="rotate(-90 60 60)"
          style="transition: stroke-dashoffset 1.2s cubic-bezier(0.16,1,0.3,1); filter: drop-shadow(0 0 8px currentColor);"/>
        <text x="60" y="56" text-anchor="middle" :class="primary ? 'text-[32px]' : 'text-[22px]'" class="font-bold" fill="rgba(255,255,255,0.9)">{{ displayValue }}</text>
        <text x="60" y="74" text-anchor="middle" class="text-[10px] font-medium" fill="rgba(255,255,255,0.35)">分</text>
      </svg>
      <span class="block text-xs text-white/40 font-medium mt-0.5">{{ label }}</span>
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
      step: 'upload',
      loading: false,
      error: null,

      isDragover: false,
      resumeId: '',
      fileInfo: { fileName: '', pages: 0 },
      cleanedText: '',

      extractedInfo: null,
      extractStatusText: '',
      _extractMsgIdx: 0,
      _extractMsgTimer: null,

      jobDescription: '',
      matchResult: null,
      displayScores: { total: 0, skill: 0, experience: 0, education: 0 },

      apiOnline: false,
      _errorTimer: null,
    }
  },

  computed: {
    infoCards() {
      if (!this.extractedInfo) return []
      const cards = []
      const info = this.extractedInfo

      if (info.name !== undefined)
        cards.push({ label: '姓名', value: this.esc(info.name || '—'), wide: false })
      if (info.phone !== undefined)
        cards.push({ label: '电话', value: this.esc(info.phone || '—'), wide: false })
      if (info.email !== undefined)
        cards.push({ label: '邮箱', value: this.esc(info.email || '—'), wide: false })
      if (info.address !== undefined)
        cards.push({ label: '地址', value: this.esc(info.address || '—'), wide: false })
      if (info.jobIntention !== undefined)
        cards.push({ label: '求职意向', value: this.esc(info.jobIntention || '—'), wide: false })
      if (info.workYears !== undefined)
        cards.push({ label: '工作年限', value: this.esc(info.workYears != null ? info.workYears + ' 年' : '—'), wide: false })

      if (info.education) {
        const edu = [
          info.education.degree, info.education.school, info.education.major,
          info.education.graduationYear ? info.education.graduationYear + '年毕业' : '',
        ].filter(Boolean).join(' · ') || '—'
        cards.push({ label: '教育背景', value: this.esc(edu), wide: true })
      }

      if (info.projects && info.projects.length) {
        const html = '<ul class="space-y-1.5 mt-1">' +
          info.projects.map(p =>
            '<li class="text-sm text-white/50 py-1 border-b border-white/[0.03] last:border-0">' +
            '<strong class="text-white/70">' + this.esc(p.name) + '</strong>' +
            (p.role ? ' <span class="text-white/30">— ' + this.esc(p.role) + '</span>' : '') +
            (p.techStack && p.techStack.length
              ? ' <span class="inline-flex gap-1 ml-1.5">' + p.techStack.map(t =>
                '<span class="text-[10px] font-medium px-1.5 py-0.5 rounded bg-indigo-500/10 text-indigo-300 border border-indigo-500/20">' + this.esc(t) + '</span>'
              ).join('') + '</span>'
              : '') +
            '</li>'
          ).join('') + '</ul>'
        cards.push({ label: '项目经历 (' + info.projects.length + ')', value: html, wide: true })
      }

      return cards
    },
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
    esc(str) {
      if (str == null) return '—'
      return String(str).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;')
    },

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
      if (!res.ok) throw new Error('HTTP ' + res.status)
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

    onDropZoneMouseMove(e) {
      const zone = e.currentTarget
      const rect = zone.getBoundingClientRect()
      const x = (e.clientX - rect.left) / rect.width * 100
      const y = (e.clientY - rect.top) / rect.height * 100
      zone.style.setProperty('--mx', x + '%')
      zone.style.setProperty('--my', y + '%')
    },

    triggerFileInput() { this.$refs.fileInput.click() },

    handleFileSelect(e) {
      const f = e.target.files[0]
      if (f) this.uploadFile(f)
    },

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

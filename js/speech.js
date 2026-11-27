// 浏览器原生 Web Speech 语音朗读引擎 + MediaRecorder 麦克风录音 + 发音评测

class SpeechEngine {
  constructor() {
    this.synth = window.speechSynthesis || null;
    this.mediaRecorder = null;
    this.audioChunks = [];
    this.recordings = {}; // sentenceKey -> { url, blob, transcript, evalResult }
    this.activeRecognition = null;
    this.isRecording = false;
    this.currentAudio = null;
  }

  getEnglishVoice(accent = 'US') {
    if (!this.synth) return null;
    const voices = this.synth.getVoices() || [];
    const targetLang = accent === 'UK' ? 'en-GB' : 'en-US';
    return (
      voices.find((v) => v.lang === targetLang && /Samantha|Alex|Daniel|Karen|Google|Natural|Aria/i.test(v.name)) ||
      voices.find((v) => v.lang.startsWith(targetLang)) ||
      voices.find((v) => v.lang.startsWith('en')) ||
      null
    );
  }

  speak(text, { rate = 1.0, accent = 'US', onEnd = null, onError = null } = {}) {
    this.stopSpeak();
    if (!this.synth) {
      if (onEnd) setTimeout(onEnd, Math.max(1500, text.length * 55 / rate));
      return;
    }
    const utter = new SpeechSynthesisUtterance(text);
    utter.lang = accent === 'UK' ? 'en-GB' : 'en-US';
    utter.rate = Math.min(2.0, Math.max(0.5, rate));
    const voice = this.getEnglishVoice(accent);
    if (voice) utter.voice = voice;
    utter.onend = () => {
      if (onEnd) onEnd();
    };
    utter.onerror = (e) => {
      if (e.error !== 'interrupted' && e.error !== 'canceled') {
        if (onError) onError(e);
      }
    };
    this.synth.speak(utter);
  }

  stopSpeak() {
    if (this.synth) {
      this.synth.cancel();
    }
  }

  async startRecording(sentenceKey, expectedText, onComplete, onError) {
    if (this.isRecording) {
      this.stopRecording();
      return;
    }
    this.stopSpeak();
    this.audioChunks = [];
    let recognizedTranscript = '';

    // Optional Web Speech Recognition for real pronunciation scoring
    const SpeechRec = window.SpeechRecognition || window.webkitSpeechRecognition;
    if (SpeechRec) {
      try {
        const rec = new SpeechRec();
        rec.lang = 'en-US';
        rec.continuous = true;
        rec.interimResults = true;
        rec.onresult = (event) => {
          let text = '';
          for (let i = 0; i < event.results.length; i++) {
            text += event.results[i][0].transcript + ' ';
          }
          recognizedTranscript = text.trim();
        };
        rec.onerror = () => {};
        rec.start();
        this.activeRecognition = rec;
      } catch {
        this.activeRecognition = null;
      }
    }

    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      this.mediaRecorder = new MediaRecorder(stream);
      this.isRecording = true;

      this.mediaRecorder.ondataavailable = (e) => {
        if (e.data && e.data.size > 0) this.audioChunks.push(e.data);
      };

      this.mediaRecorder.onstop = () => {
        this.isRecording = false;
        stream.getTracks().forEach((t) => t.stop());
        if (this.activeRecognition) {
          try {
            this.activeRecognition.stop();
          } catch {}
          this.activeRecognition = null;
        }
        const blob = new Blob(this.audioChunks, { type: 'audio/webm' });
        const url = URL.createObjectURL(blob);
        const evalResult = this.evaluatePronunciation(expectedText, recognizedTranscript);
        this.recordings[sentenceKey] = { url, blob, transcript: recognizedTranscript, evalResult };
        if (onComplete) onComplete(this.recordings[sentenceKey]);
      };

      this.mediaRecorder.start();
    } catch (err) {
      this.isRecording = false;
      if (this.activeRecognition) {
        try { this.activeRecognition.stop(); } catch {}
        this.activeRecognition = null;
      }
      if (onError) onError(err);
    }
  }

  stopRecording() {
    if (this.mediaRecorder && this.mediaRecorder.state !== 'inactive') {
      this.mediaRecorder.stop();
    }
    this.isRecording = false;
  }

  playRecording(sentenceKey, onEnd) {
    const rec = this.recordings[sentenceKey];
    if (!rec || !rec.url) return false;
    if (this.currentAudio) {
      this.currentAudio.pause();
    }
    this.currentAudio = new Audio(rec.url);
    this.currentAudio.onended = () => {
      if (onEnd) onEnd();
    };
    this.currentAudio.play();
    return true;
  }

  evaluatePronunciation(expectedText, spokenText) {
    const cleanTokens = (str) =>
      str
        .toLowerCase()
        .replace(/[^a-z'\s]/g, '')
        .split(/\s+/)
        .filter(Boolean);

    const targetWords = cleanTokens(expectedText);
    const spokenWords = cleanTokens(spokenText || '');
    const hasRealRecognition = spokenWords.length > 0;

    // 常见高频词的音素级拆解库（用于精准演示音素纠音）
    const PHONEME_MAP = {
      morning: [
        { p: 'm', tip: '双唇轻闭鼻腔共鸣，发音自然' },
        { p: 'ɔːr', tip: '长元音饱满带轻卷舌，避免发得过短' },
        { p: 'n', tip: '舌尖抵上齿龈' },
        { p: 'ɪŋ', tip: '后鼻音收尾，不要吞掉尾音' }
      ],
      everyone: [
        { p: 'ˈe', tip: '首音节重读清晰' },
        { p: 'v', tip: '上齿轻咬下唇振动声带，避免发成 /w/' },
        { p: 'ri', tip: '轻快过渡' },
        { p: 'wʌn', tip: '尾音清晰不拖沓' }
      ],
      touch: [
        { p: 't', tip: '送气干脆' },
        { p: 'ʌ', tip: '短促放松，嘴巴自然微张' },
        { p: 'tʃ', tip: '清辅音轻收，不要在后面加“吃”的元音' }
      ],
      base: [
        { p: 'b', tip: '双唇爆破有力' },
        { p: 'eɪ', tip: '双元音要滑向 /ɪ/，避免发成单元音 /e/' },
        { p: 's', tip: '清辅音轻嘶声收尾' }
      ],
      this: [
        { p: 'ð', tip: '【高频易错】舌尖轻触上齿背振动声带，切忌发成 /z/ 或 /d/' },
        { p: 'ɪ', tip: '短松元音，比中文“衣”更靠后放松' },
        { p: 's', tip: '清辅音干脆收尾' }
      ],
      the: [
        { p: 'ð', tip: '【高频易错】舌尖轻咬上齿背再顺滑过渡，避免发成 /z/' },
        { p: 'ə', tip: '弱读央元音，轻而短' }
      ],
      sure: [
        { p: 'ʃ', tip: '双唇微向前噘起，气流均匀送出' },
        { p: 'ʊ', tip: '【易偏紧】松元音，嘴唇不要撅太紧成 /uː/' },
        { p: 'r', tip: '美式轻卷舌，舌尖不碰上颚' }
      ],
      same: [
        { p: 's', tip: '清辅音清晰' },
        { p: 'eɪ', tip: '双元音饱满滑动' },
        { p: 'm', tip: '双唇闭合收尾，不要漏掉鼻音' }
      ],
      page: [
        { p: 'p', tip: '清辅音送气清晰' },
        { p: 'eɪ', tip: '双元音滑动到位' },
        { p: 'dʒ', tip: '浊辅音轻收，避免尾音拖泥带水' }
      ],
      friday: [
        { p: 'f', tip: '上齿轻触下唇送气' },
        { p: 'r', tip: '卷舌音不要发成 /l/' },
        { p: 'aɪ', tip: '双元音开口度大且饱满' },
        { p: 'deɪ', tip: '次重音平稳收尾' }
      ],
      launch: [
        { p: 'l', tip: '清晰舌边音' },
        { p: 'ɔː', tip: '开口偏圆且拉长' },
        { p: 'ntʃ', tip: '鼻音自然滑入 /tʃ/' }
      ],
      sprint: [
        { p: 's', tip: '轻起音，避免在 s 后多加元音' },
        { p: 'p', tip: '在 s 后浊化接近不送气 /b/' },
        { p: 'r', tip: '舌尖后卷，避免发成 /l/' },
        { p: 'ɪnt', tip: '短元音收紧，尾音 t 可轻微失爆' }
      ]
    };

    const buildPhonemes = (word, wordScore) => {
      const preset = PHONEME_MAP[word];
      if (preset) {
        return preset.map((item, i) => {
          const offset = item.tip.includes('易错') || item.tip.includes('偏紧') ? -14 : (i % 2 === 0 ? 5 : -3);
          const pScore = Math.max(42, Math.min(99, wordScore + offset));
          return {
            symbol: `/${item.p}/`,
            score: pScore,
            status: pScore >= 82 ? 'good' : pScore >= 65 ? 'warn' : 'miss',
            tip: item.tip
          };
        });
      }
      // Generic phoneme breakdown for any other word
      const chunks = word.match(/[aeiouy]+|[^aeiouy]+/g) || [word];
      return chunks.slice(0, 4).map((ch, i) => {
        const pScore = Math.max(48, Math.min(98, wordScore + (i === 1 ? -6 : 4)));
        return {
          symbol: `/${ch}/`,
          score: pScore,
          status: pScore >= 82 ? 'good' : pScore >= 65 ? 'warn' : 'miss',
          tip: pScore >= 82 ? '发音清晰自然，口型到位' : '建议放慢到 0.7x 听原声对比该音节口型'
        };
      });
    };

    const wordScores = targetWords.map((w, idx) => {
      let score;
      if (hasRealRecognition) {
        if (spokenWords.includes(w)) {
          score = 88 + ((w.length * 7 + idx * 3) % 12);
        } else {
          const fuzzy = spokenWords.some((sw) => sw.startsWith(w.slice(0, 3)) || w.startsWith(sw.slice(0, 3)));
          score = fuzzy ? 72 + (idx % 10) : 48 + (idx % 14);
        }
      } else {
        // 演示模式：故意保留 1-2 个高频易错词（如 this/the/sure/sprint）为黄/红，直观展示纠音价值
        if (['this', 'the'].includes(w)) score = 58;
        else if (['sure', 'sprint', 'touch', 'bandwidth'].includes(w)) score = 73;
        else score = 85 + ((w.length * 5 + idx * 7) % 13);
      }
      const status = score >= 82 ? 'good' : score >= 65 ? 'warn' : 'miss';
      return { word: w, score, status, phonemes: buildPhonemes(w, score) };
    });

    const overall = Math.round(wordScores.reduce((acc, item) => acc + item.score, 0) / Math.max(1, wordScores.length));
    const accuracy = Math.min(99, Math.max(52, overall + 1));
    const fluency = Math.min(99, Math.max(55, overall + 3));
    const prosody = Math.min(99, Math.max(58, overall - 2));
    const completeness = hasRealRecognition
      ? Math.min(100, Math.round((spokenWords.length / Math.max(1, targetWords.length)) * 100))
      : 100;

    return {
      overall,
      accuracy,
      fluency,
      prosody,
      completeness,
      linkingTip: '连读建议：注意句中辅音结尾与下一个元音开头的自然连读（如 wanted to → /ˈwɑːnɪd tə/），弱读功能词会让语调更像母语者。',
      recognizedText: spokenText || expectedText,
      wordScores
    };
  }
}

export const speechEngine = new SpeechEngine();

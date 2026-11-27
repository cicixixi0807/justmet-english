// Just Met 宇宙 — 精选日常与职场英语听说课程库与词典数据
import { LOCAL_EPISODES } from './local_episodes.js';

export const THEMES = [
  { id: 'justmet-blush', name: 'Just Met 柔粉奶油', bg: '#FBF7F2', card: '#FFFFFF', border: '#EAD8D1', text: '#2B1F1B', muted: '#755E57', accent: '#C86A5B', accentSoft: '#F6E3DE', dark: false },
  { id: 'warm-ivory', name: 'Warm Ivory 暖象牙', bg: '#F7F2E8', card: '#FBF8F1', border: '#E4D9C8', text: '#2B2118', muted: '#6E5D4F', accent: '#C67D38', accentSoft: '#F3E3CF', dark: false },
  { id: 'oat-linen', name: '燕麦亚麻', bg: '#F4F1EC', card: '#FCFBF9', border: '#E0DAD0', text: '#2C2A27', muted: '#6F6B64', accent: '#8E6B4E', accentSoft: '#EAE0D5', dark: false },
  { id: 'matcha-mist', name: '抹茶护眼', bg: '#EFF5F0', card: '#F9FCF9', border: '#D4E4D8', text: '#1E2D24', muted: '#566E60', accent: '#4A8B65', accentSoft: '#DCEEE2', dark: false },
  { id: 'cloud-blue', name: '晴空海盐', bg: '#F0F5FA', card: '#FAFCFF', border: '#D5E2F0', text: '#1D2939', muted: '#5A6B82', accent: '#3B74B8', accentSoft: '#DDEAF8', dark: false },
  { id: 'lavender-tea', name: '紫苏奶盖', bg: '#F5F2F9', card: '#FCFBFD', border: '#E2DAE9', text: '#292136', muted: '#695C7A', accent: '#7D5BA6', accentSoft: '#EAE2F5', dark: false },
  { id: 'peach-latte', name: '蜜桃拿铁', bg: '#FDF3EE', card: '#FFFBF9', border: '#F0D9CE', text: '#32201A', muted: '#7B5F55', accent: '#D47451', accentSoft: '#FBE3D8', dark: false },
  { id: 'paper-white', name: '极简宣纸', bg: '#F8F9FA', card: '#FFFFFF', border: '#E5E7EB', text: '#18181B', muted: '#6B7280', accent: '#2563EB', accentSoft: '#DBEAFE', dark: false },
  { id: 'espresso-night', name: '深夜书房', bg: '#1B1715', card: '#25201D', border: '#3A322D', text: '#F5ECE6', muted: '#A9998E', accent: '#E0926C', accentSoft: '#3B2B23', dark: true },
  { id: 'midnight-slate', name: '静谧深蓝', bg: '#0F172A', card: '#1E293B', border: '#334155', text: '#F1F5F9', muted: '#94A3B8', accent: '#60A5FA', accentSoft: '#1E3A5F', dark: true },
  { id: 'forest-dusk', name: '松林夜读', bg: '#141E1A', card: '#1D2B25', border: '#2D4138', text: '#ECF4F0', muted: '#94AEA1', accent: '#6BBF92', accentSoft: '#223B2F', dark: true },
  { id: 'rose-velvet', name: '玫瑰天鹅绒', bg: '#211619', card: '#2D1F23', border: '#442E34', text: '#F9ECEF', muted: '#BCA0A7', accent: '#E58A94', accentSoft: '#44262C', dark: true },
];

export const DICTIONARY = {
  'catch up': {
    headword: 'catch up',
    pos: 'verb phrase',
    type: 'expression',
    level: '日常高频',
    us: '/kætʃ ʌp/',
    uk: '/kætʃ ʌp/',
    meanings: [
      { en: 'To talk to someone you have not seen for some time and find out what they have been doing.', zh: '叙旧；聊聊近况；互通消息' },
      { en: 'To reach the same standard or stage as someone else.', zh: '赶上；追上进度' }
    ],
    exampleEn: "It's been ages! Let's grab coffee this weekend and catch up.",
    exampleZh: '好久不见了！这周末一起喝杯咖啡叙叙旧吧。'
  },
  'swamped': {
    headword: 'swamped',
    pos: 'adjective',
    type: 'vocab',
    level: '职场高频',
    us: '/swɑːmpt/',
    uk: '/swɒmpt/',
    meanings: [
      { en: 'Having too much to do; overwhelmed with work or tasks.', zh: '忙得不可开交的；被工作淹没的' }
    ],
    exampleEn: "I'm completely swamped with deadlines this week.",
    exampleZh: '我这周被各种截止日期搞得忙得不可开交。'
  },
  'on the same page': {
    headword: 'on the same page',
    pos: 'idiom',
    type: 'expression',
    level: '商务核心',
    us: '/ɑːn ðə seɪm peɪdʒ/',
    uk: '/ɒn ðə seɪm peɪdʒ/',
    meanings: [
      { en: 'Sharing the same understanding or agreement about a plan or situation.', zh: '达成共识；想法一致；步调同步' }
    ],
    exampleEn: "Before we kick off the campaign, let's make sure everyone is on the same page.",
    exampleZh: '在启动活动之前，我们先确保大家达成共识。'
  },
  'circle back': {
    headword: 'circle back',
    pos: 'verb phrase',
    type: 'expression',
    level: '商务高频',
    us: '/ˈsɜːrkl bæk/',
    uk: '/ˈsɜːkl bæk/',
    meanings: [
      { en: 'To return to a topic or person later to discuss or follow up.', zh: '稍后再讨论；回头跟进' }
    ],
    exampleEn: "Let me check with the design team and circle back to you by Friday.",
    exampleZh: '我先和设计团队确认一下，周五前再回头跟你跟进。'
  },
  'bandwidth': {
    headword: 'bandwidth',
    pos: 'noun',
    type: 'vocab',
    level: '职场地道',
    us: '/ˈbændwɪdθ/',
    uk: '/ˈbændwɪdθ/',
    meanings: [
      { en: 'The energy, time, or mental capacity available to deal with a task.', zh: '（人的）精力、时间余量；处理能力' }
    ],
    exampleEn: "I'd love to help, but I honestly don't have the bandwidth right now.",
    exampleZh: '我很想帮忙，但现在实在抽不出精力了。'
  },
  'takeaway': {
    headword: 'takeaway',
    pos: 'noun',
    type: 'vocab',
    level: '会议常用',
    us: '/ˈteɪkəweɪ/',
    uk: '/ˈteɪkəweɪ/',
    meanings: [
      { en: 'A key fact, point, or idea to be remembered from a meeting or discussion.', zh: '核心要点；收获；结论' }
    ],
    exampleEn: 'The main takeaway from user interviews is that onboarding feels too long.',
    exampleZh: '用户访谈的核心结论是新手引导流程太长了。'
  },
  'touch base': {
    headword: 'touch base',
    pos: 'verb phrase',
    type: 'expression',
    level: '商务高频',
    us: '/tʌtʃ beɪs/',
    uk: '/tʌtʃ beɪs/',
    meanings: [
      { en: 'To briefly make contact with someone to update or check in.', zh: '简短联系；碰个头；同步一下情况' }
    ],
    exampleEn: 'Just wanted to touch base before our client pitch tomorrow.',
    exampleZh: '明天见客户提案前，想先跟你简单碰个头。'
  },
  'low-key': {
    headword: 'low-key',
    pos: 'adverb / adj.',
    type: 'vocab',
    level: '美式口语',
    us: '/ˌloʊˈkiː/',
    uk: '/ˌləʊˈkiː/',
    meanings: [
      { en: 'Quietly, subtly, or somewhat; not flashy or intense.', zh: '低调的；隐约有点；悄悄地' }
    ],
    exampleEn: "I'm low-key nervous about speaking in front of two hundred people.",
    exampleZh: '要在两百人面前演讲，我其实隐约有点紧张。'
  },
  'hit it off': {
    headword: 'hit it off',
    pos: 'verb phrase',
    type: 'expression',
    level: '社交高频',
    us: '/hɪt ɪt ɔːf/',
    uk: '/hɪt ɪt ɒf/',
    meanings: [
      { en: 'To quickly become friendly and get along very well with someone.', zh: '一见如故；很投缘；聊得来' }
    ],
    exampleEn: 'We met at a coffee workshop and immediately hit it off.',
    exampleZh: '我们在一次咖啡沙龙认识，立刻就一见如故。'
  },
  'vibe': {
    headword: 'vibe',
    pos: 'noun',
    type: 'vocab',
    level: '日常高频',
    us: '/vaɪb/',
    uk: '/vaɪb/',
    meanings: [
      { en: 'The atmosphere or emotional feeling of a place, person, or conversation.', zh: '氛围；气场；感觉' }
    ],
    exampleEn: 'This little bookstore has such a cozy, creative vibe.',
    exampleZh: '这家小书店的氛围特别温暖有创意。'
  },
  'boundary': {
    headword: 'boundary',
    pos: 'noun',
    type: 'vocab',
    level: '成长/职场',
    us: '/ˈbaʊndri/',
    uk: '/ˈbaʊndri/',
    meanings: [
      { en: 'A personal limit that defines what behavior you are comfortable with.', zh: '边界感；底线；界限' }
    ],
    exampleEn: 'Setting healthy boundaries at work prevents burnout.',
    exampleZh: '在职场建立健康的边界感能有效防止职业倦怠。'
  },
  'burnout': {
    headword: 'burnout',
    pos: 'noun',
    type: 'vocab',
    level: '职场高频',
    us: '/ˈbɜːrnaʊt/',
    uk: '/ˈbɜːnaʊt/',
    meanings: [
      { en: 'Physical or mental exhaustion caused by prolonged stress or overwork.', zh: '职业倦怠；身心俱疲' }
    ],
    exampleEn: 'Taking a real weekend off is essential to avoid burnout.',
    exampleZh: '周末真正放空休息对避免职业倦怠至关重要。'
  },
  'push back': {
    headword: 'push back',
    pos: 'verb phrase',
    type: 'expression',
    level: '商务核心',
    us: '/pʊʃ bæk/',
    uk: '/pʊʃ bæk/',
    meanings: [
      { en: 'To delay an event or deadline to a later time.', zh: '推迟；延后' },
      { en: 'To politely resist or disagree with an unreasonable request.', zh: '礼貌拒绝；提出异议' }
    ],
    exampleEn: 'Can we push back the launch by two days to finish QA testing?',
    exampleZh: '我们可以把上线时间往后推两天，先把测试做完吗？'
  },
  'small talk': {
    headword: 'small talk',
    pos: 'noun phrase',
    type: 'expression',
    level: '社交高频',
    us: '/ˈsmɔːl tɔːk/',
    uk: '/ˈsmɔːl tɔːk/',
    meanings: [
      { en: 'Polite, light conversation about everyday topics used to break the ice.', zh: '闲聊；寒暄；破冰聊天' }
    ],
    exampleEn: 'Good small talk makes networking events feel way less awkward.',
    exampleZh: '得体的破冰闲聊会让社交活动显得自然得多。'
  },
  'break the ice': {
    headword: 'break the ice',
    pos: 'idiom',
    type: 'expression',
    level: '社交核心',
    us: '/breɪk ði aɪs/',
    uk: '/breɪk ði aɪs/',
    meanings: [
      { en: 'To do or say something to relieve tension and start a friendly conversation.', zh: '打破僵局；破冰' }
    ],
    exampleEn: 'Asking about someone’s favorite local restaurant is an easy way to break the ice.',
    exampleZh: '问对方最喜欢本地哪家餐厅，是个很轻松的破冰方式。'
  },
  'wing it': {
    headword: 'wing it',
    pos: 'verb phrase',
    type: 'expression',
    level: '地道口语',
    us: '/wɪŋ ɪt/',
    uk: '/wɪŋ ɪt/',
    meanings: [
      { en: 'To improvise and do something without much prior preparation.', zh: '即兴发挥；临场应对' }
    ],
    exampleEn: 'My slides failed to load, so I just had to wing it.',
    exampleZh: '我的幻灯片没加载出来，只好临场即兴发挥了。'
  },
  'figure out': {
    headword: 'figure out',
    pos: 'verb phrase',
    type: 'expression',
    level: '日常高频',
    us: '/ˈfɪɡjər aʊt/',
    uk: '/ˈfɪɡər aʊt/',
    meanings: [
      { en: 'To understand or solve something after thinking about it.', zh: '弄明白；想出办法；搞清楚' }
    ],
    exampleEn: "Don't worry, we'll figure out a smooth workaround together.",
    exampleZh: '别担心，我们一起想个顺畅的替代方案。'
  },
  'overthinking': {
    headword: 'overthinking',
    pos: 'noun / verb',
    type: 'vocab',
    level: '情感/日常',
    us: '/ˌoʊvərˈθɪŋkɪŋ/',
    uk: '/ˌəʊvəˈθɪŋkɪŋ/',
    meanings: [
      { en: 'Thinking about something too much or for too long, often causing anxiety.', zh: '过度思考；内耗；想太多' }
    ],
    exampleEn: 'Sometimes overthinking a simple text message ruins your whole evening.',
    exampleZh: '有时候为一条简单的短信想太多，会毁掉一整晚的心情。'
  },
  'genuine': {
    headword: 'genuine',
    pos: 'adjective',
    type: 'vocab',
    level: '高频形容词',
    us: '/ˈdʒenjuɪn/',
    uk: '/ˈdʒenjuɪn/',
    meanings: [
      { en: 'Sincere, honest, and authentic rather than fake.', zh: '真诚的；发自内心的；真正的' }
    ],
    exampleEn: 'People can always tell when a compliment is genuine.',
    exampleZh: '赞美是不是发自内心的，别人其实总能感受得到。'
  },
  'stand out': {
    headword: 'stand out',
    pos: 'verb phrase',
    type: 'expression',
    level: '面试/职场',
    us: '/stænd aʊt/',
    uk: '/stænd aʊt/',
    meanings: [
      { en: 'To be noticeably better, clearer, or more memorable than others.', zh: '脱颖而出；引人注目' }
    ],
    exampleEn: 'Sharing a specific project story helps you stand out in interviews.',
    exampleZh: '分享一个具体的项目故事能帮你在面试中脱颖而出。'
  },
  'walk through': {
    headword: 'walk through',
    pos: 'verb phrase',
    type: 'expression',
    level: '面试/会议',
    us: '/wɔːk θruː/',
    uk: '/wɔːk θruː/',
    meanings: [
      { en: 'To explain a process, resume, or plan step by step.', zh: '一步步讲解；带大家梳理一遍' }
    ],
    exampleEn: 'Could you walk me through how you handled that launch?',
    exampleZh: '能带我一步步讲讲你当时是怎么推进那次上线的吗？'
  },
  'aligned': {
    headword: 'aligned',
    pos: 'adjective',
    type: 'vocab',
    level: '商务高频',
    us: '/əˈlaɪnd/',
    uk: '/əˈlaɪnd/',
    meanings: [
      { en: 'In agreement and working toward the same goal.', zh: '目标一致的；对齐的' }
    ],
    exampleEn: 'Once product and marketing are aligned, execution moves fast.',
    exampleZh: '一旦产品和市场目标对齐，执行起来就会非常快。'
  }
};

export const UPSELL_PACKS = [
  {
    id: 'pack-ai-credits',
    badge: '高频复购 · 消耗型',
    title: 'AI 发音音素级精评 · 30 积分加油包',
    price: '¥19.9',
    unit: '/ 30 次精评',
    desc: '针对每一句跟读提供逐词音素级纠音、重音与连读诊断、流利度打分及原声对比，按需加购、用完复购。',
    demoCode: 'JM-AI-30',
    perks: ['30 次 AI 逐词音素级深度评测', '自动定位弱读/漏读/重音偏差词', '永久有效，支持小红书橱窗领码充值']
  },
  {
    id: 'pack-ai-coach',
    badge: '最受欢迎 · 提效包',
    title: 'AI 1v1 情景口语陪练 + 错题抗遗忘复习',
    price: '¥49',
    unit: '/ 季卡',
    desc: '学完每集立刻进入 AI 真实情景对话把地道表达用出来；自动汇总听写错词与低分句，生成每日 5 分钟艾宾浩斯复习计划。',
    demoCode: 'JM-PRO-2026',
    perks: ['300 集全场景 AI 1v1 角色扮演陪练', 'AI 实时润色：给出更高情商的职场/日常替代表达', '智能错题本 + 抗遗忘曲线复习 + 赠 30 点评测积分']
  },
  {
    id: 'pack-pro-notes',
    badge: '高客单 · 陪伴/进阶',
    title: '连读弱读精讲插件 + Just met 主题共读营',
    price: '¥169',
    unit: '/ 季',
    desc: '解锁全站「美式连读/吞音标注 + 同场景三档礼貌度替换句型 + Anki/Notion 一键导出」，并享季度主题口语打卡营席位。',
    demoCode: 'JM-VIP-2026',
    perks: ['开启全站连读/弱读/语调符号精讲视图', '支持 Anki 记忆卡 & Notion 讲义一键导出', '季度主题口语共读陪伴 + 每月 50 点 AI 评测积分']
  }
];

export const LIBRARIES = [
  {
    id: 'justmet-english-1',
    title: '刚认识小屋 · 英语自习室',
    subtitle: 'cici · Eddie 主理精选 · 共 300 期持续更新',
    description: '由 cici · Eddie 主理严选，持续更新 300 期高口碑英文精听跟读视频。覆盖日常对话、生活英语、美食、旅行、购物、名人访谈与个人成长，1–5 星科学难度分级，每天 10 分钟自然练出地道口语。',
    type: '情景对话 & 精听',
    coverGradient: 'linear-gradient(135deg, #F6E3DE 0%, #E8B4A6 55%, #C86A5B 100%)',
    updatedAt: '2026/11/26',
    totalPlanned: 300,
    tags: ['日常对话', '生活英语', '美食', '旅行', '名人访谈', '购物', '个人成长', '生活'],
    episodes: []
  }
];

export function findEpisodeById(episodeId) {
  for (const lib of LIBRARIES) {
    const ep = lib.episodes.find((e) => e.id === episodeId);
    if (ep) return { library: lib, episode: ep };
  }
  return { library: LIBRARIES[0], episode: LIBRARIES[0].episodes[0] };
}

// 自动把外接硬盘同步生成的真实剧集载入资料库
if (Array.isArray(LOCAL_EPISODES) && LOCAL_EPISODES.length > 0) {
  LIBRARIES[0].episodes.push(...LOCAL_EPISODES);
}

const DICT_LOCAL_STORAGE_KEY = 'justmet_dict_cache_v1';

export function getCachedWord(rawWord) {
  const clean = String(rawWord || '').toLowerCase().trim().replace(/^[^a-z'-]+|[^a-z'-]+$/g, '');
  if (!clean) return null;
  if (DICTIONARY[clean]) return DICTIONARY[clean];
  try {
    const cache = JSON.parse(localStorage.getItem(DICT_LOCAL_STORAGE_KEY) || '{}');
    if (cache[clean]) return cache[clean];
  } catch {}
  return null;
}

export function saveCachedWord(rawWord, entry) {
  const clean = String(rawWord || '').toLowerCase().trim().replace(/^[^a-z'-]+|[^a-z'-]+$/g, '');
  if (!clean || !entry) return;
  try {
    const cache = JSON.parse(localStorage.getItem(DICT_LOCAL_STORAGE_KEY) || '{}');
    cache[clean] = entry;
    localStorage.setItem(DICT_LOCAL_STORAGE_KEY, JSON.stringify(cache));
  } catch {}
}

export function lookupWord(rawWord) {
  return getCachedWord(rawWord);
}

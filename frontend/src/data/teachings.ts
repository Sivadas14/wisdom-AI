/**
 * Static data for the five sacred texts in the Guided Introduction to the Teachings.
 * Each teaching has a short teaser (shown on the card) and a full introduction
 * (shown in the modal). The introduction is also read aloud via Web Speech API.
 */

export interface Teaching {
  id: string;
  title: string;
  sanskrit: string;
  author: string;
  era: string;
  teaser: string;
  introduction: string;
  chatPrompt: string;
}

export const TEACHINGS: Teaching[] = [
  {
    id: "who-am-i",
    title: "Who Am I?",
    sanskrit: "Nan Yar",
    author: "Ramana Maharshi",
    era: "1902",
    teaser:
      "There is one question that has quietly followed you your whole life — not asked out loud, but felt beneath every ambition, every relationship, every restless search for meaning.",
    introduction: `There is one question that has quietly followed you your whole life — not asked out loud, but felt beneath every ambition, every relationship, every restless search for meaning: Who, exactly, am I?

In 1902, a young Ramana Maharshi — barely twenty-two years old, already awakened — sat with a devotee who had a notebook and a list of questions. What emerged from that afternoon was a short text of profound simplicity: Who Am I? In it, Ramana does not answer the question for you. Instead, he gives you the most direct method ever devised for answering it yourself.

The practice is deceptively simple. Whenever a thought arises, instead of following it outward, you ask: To whom does this thought arise? Who is thinking this? You trace every experience back to the one who is experiencing it — and keep tracing, deeper and deeper, until you find what has been there all along: a pure, silent awareness that was never born, never troubled, and never separate from what you truly are.

This is not philosophy to be studied at a distance. It is an instruction to be lived, moment by moment, breath by breath. Most spiritual traditions point toward the light. Who Am I? tells you that you are the light — and shows you exactly how to stop looking away.

If you read only one text in your life on the nature of the Self, let it be this one.`,
    chatPrompt:
      "I've just read about 'Who Am I?' by Ramana Maharshi. Can you guide me through the practice of self-inquiry — how do I actually ask 'Who am I?' and what am I looking for?",
  },
  {
    id: "forty-verses",
    title: "Forty Verses on Reality",
    sanskrit: "Ulladu Narpadu",
    author: "Ramana Maharshi",
    era: "1928",
    teaser:
      "What is real? Not in the philosophical sense — but in the deepest, most personal sense. When everything you have believed about yourself and the world is stripped away, what remains?",
    introduction: `What is real? Not in the philosophical sense — but in the deepest, most personal sense. When everything you've believed about yourself and the world is stripped away, what remains?

Ulladu Narpadu — Forty Verses on Reality — is Ramana Maharshi's most compressed and intellectually precise teaching. Written in Tamil verse at the request of devotees who wanted his teachings in a form that could be memorized and carried in the heart, it is forty gems of insight arranged in a careful sequence, each one building on the last, each one dismantling a layer of the comfortable illusions we live inside.

Ramana starts with a question that stops the mind: Does the world exist without a seer? And does the seer exist without the Self? From there, he moves through the nature of ego, the relationship between the individual and the universe, the reality of God, and the paradox of the mind trying to understand what the mind cannot contain.

What makes this text remarkable is not its length — it can be read in twenty minutes — but its precision. Every word earns its place. Every verse is a small awakening if you sit with it honestly.

This is the text for those who want to understand, not just feel — those for whom the heart and the intellect both need to be satisfied before something can be called true. Ramana satisfies both, completely, in forty verses.

Read it once for the ideas. Read it again for the silence that opens behind them.`,
    chatPrompt:
      "I've just read about the 'Forty Verses on Reality' by Ramana Maharshi. Can you walk me through some of the key verses — especially the ones about the nature of the self and the world?",
  },
  {
    id: "upadesa-saram",
    title: "The Essence of Instruction",
    sanskrit: "Upadesa Saram",
    author: "Ramana Maharshi",
    era: "1927",
    teaser:
      "Every spiritual tradition seems to offer a different path — devotion, service, breath, mantra, meditation, inquiry. If you have explored more than one, you may have wondered: are these all going to the same place?",
    introduction: `Every spiritual tradition — Hindu, Buddhist, Sufi, Christian mystical — seems to offer a different path. Devotion. Service. Breath. Mantra. Meditation. Inquiry. If you have explored more than one, you may have wondered: are these all going to the same place? And if so, what is that place?

Upadesa Saram — The Essence of Instruction — is Ramana Maharshi's answer. In thirty exquisite verses, he surveys the full landscape of spiritual practice and shows with calm clarity how every authentic path, followed to its deepest conclusion, arrives at the same recognition: there is a Self at the center of all experience, and when the seeker finally finds it, the seeker dissolves into it. The journey ends. The traveller disappears. Only the destination remains — and it was never somewhere else.

Originally composed as the philosophical heart of a longer poem, Upadesa Saram stands completely on its own. Ramana begins with action and karma, moves through devotion and surrender, arrives at meditation and breath, and culminates in pure self-inquiry — the direct recognition of what you are.

What is remarkable is the tone: no condescension toward any path, no elevation of one over another. Ramana knew that different people need different doors. This text is a map of all the doors, and a quiet pointer to what they all open into.

Whatever tradition you come from — or none at all — this text has something to say directly to you.`,
    chatPrompt:
      "I've just read about 'Upadesa Saram' by Ramana Maharshi. I'd like to understand how he sees different spiritual paths — karma, bhakti, yoga, and jnana — and how they all lead to the same recognition.",
  },
  {
    id: "devikalottara",
    title: "The Supreme Wisdom",
    sanskrit: "Devikalottara",
    author: "Ancient Scripture · Translated by Ramana Maharshi",
    era: "Ancient",
    teaser:
      "Imagine a conversation at the edge of everything — between Shiva, the god of consciousness itself, and Devi, who asks him with complete sincerity: What is the highest wisdom? How does one become free?",
    introduction: `Imagine a conversation at the edge of everything — between Shiva, the god of consciousness itself, and Devi, the goddess who is his own divine energy. She asks him, with complete sincerity: What is the highest wisdom? How does one become free? And Shiva, without preamble, without metaphor, tells her the absolute truth.

Devikalottara is one of the oldest and rarest texts in the Shaiva Agamic tradition — a scripture so direct that it was considered fit only for the most mature seekers. Ramana Maharshi, who prized it above most other scriptures, translated it himself from Sanskrit into Tamil and called it a complete teaching in itself. He said that for one who truly understood it, nothing more was needed.

At its heart, Devikalottara describes jnana — not as a state to be achieved through years of practice, but as a recognition of what has always been the case. The Self is not hidden. It is not distant. It is the very awareness reading these words right now.

The text offers a series of contemplative pointers — ways of holding attention, of releasing identification with thought and body, of recognizing the spacious, luminous nature of pure awareness — that are as practical today as they were when first spoken.

This is not a text for the curious. It is a text for those who are genuinely ready — those who have already sensed, perhaps in a moment of deep stillness, that there is something present that is not the mind, not the body, not the story of me.

Ramana kept returning to it. Perhaps you will too.`,
    chatPrompt:
      "I've just read about 'Devikalottara', the ancient scripture on supreme wisdom that Ramana Maharshi translated and revered. Can you share some of its core teachings on the nature of awareness and how to abide in the Self?",
  },
  {
    id: "ashtavakra-gita",
    title: "The Song of the Self",
    sanskrit: "Ashtavakra Gita",
    author: "Ancient Sanskrit Dialogue",
    era: "Ancient",
    teaser:
      "What if you were told — not as a distant possibility, but as a plain and immediate fact — that you are already free? That you have never been bound?",
    introduction: `What if you were told — not as a distant possibility, but as a plain and immediate fact — that you are already free? That you have never been bound? That everything you have sought in spiritual practice, in wisdom, in meditation, was already here, already you, from the very beginning?

This is the opening move of the Ashtavakra Gita, and it does not soften it.

Set in ancient India, it is a dialogue between the young sage Ashtavakra — whose name means crooked in eight places, for he was born deformed — and King Janaka, one of the most powerful rulers of his age. Janaka had everything the world could offer and still felt the ache of incompleteness. He came to Ashtavakra asking: How do I attain liberation? Ashtavakra looked at him and said, in effect: Liberation from what? You are already the Self. You are already free. There is nothing to attain and no one to attain it.

What follows is one of the most radical and uncompromising dialogues in the history of human wisdom. No gradual path. No stages of practice. No techniques to master. Just a direct, relentless pointing to the nature of pure awareness — the witness that is never touched by thought, never moved by circumstance, never anything other than completely at peace.

Ramana Maharshi revered this text deeply. Its message and his own were one and the same. If Ramana's Who Am I? is the door, the Ashtavakra Gita is the open sky on the other side.

Come with an open mind. You may find it unsettles everything — and that this unsettling is exactly what you needed.`,
    chatPrompt:
      "I've just read about the 'Ashtavakra Gita'. It says I am already free, already the Self. Can you help me understand what that actually means — and why most of us don't experience it that way?",
  },
];

# Kodama: Your BBB Revit Standards Assistant
## How-To Guide for Revit Users

---

## What Is Kodama?

Kodama is BBB's AI-powered Revit standards assistant, built directly into Revit. Instead of tracking down the right SharePoint page, digging through a PDF, or asking a colleague "what's our standard for...?", you can just ask Kodama.

Kodama knows BBB's Revit standards and can answer questions in plain English -- instantly, while you're working. It draws from three sources of official BBB content:

| Content Type | What It Contains | Best For |
|---|---|---|
| **Standards Pages** | Official BBB standards on SharePoint -- the definitive source of truth | "What's the standard for...?" |
| **PDF Guides** | Reference material and detailed workflow guides | "Can you explain how...?" |
| **Training Videos** | Instructional videos with transcripts | "How do I do this step by step?" |

Kodama knows which type of content to lean on depending on your question, and it will often combine sources naturally in a single answer.

---

## Getting Started

### How to Open Kodama

1. Open Revit (any project or family file works)
2. Click the **BBB** tab in the Revit ribbon at the top of your screen
3. In the **Chat** panel, click the **Standards Chat** button

The Kodama chat window will open as a floating panel. You can move and resize it freely, and it will stay on top of Revit while you work.

### First-Time Use: Accepting the Disclaimer

The very first time you open Kodama, you will see a brief disclaimer window explaining what the tool is and how it uses AI. Read through it, then click **Accept** to continue. You only need to do this once -- Kodama remembers your acceptance going forward.

If you have questions about the tool before accepting, there is a **Learn More** link in the disclaimer that takes you to the Kodama page on the BBB intranet.

---

## The Chat Window at a Glance

When you open Kodama, you'll see:

- **A welcome message** with three suggested questions to get you started quickly
- **A text box at the bottom** where you type your question
- **A Send button** (or press **Ctrl+Enter**) to submit your question
- **A sidebar** on the left that shows your past chat sessions (click the arrow button to expand or collapse it)
- **A settings icon** in the top-right corner to personalize your experience

Kodama will greet you by name if your Windows username is detected -- and you can always update what name it uses in Settings.

---

## Asking Questions

Just type your question in plain English and press **Ctrl+Enter** or click **Send**. There is no special syntax or command to learn.

### Great Questions to Ask

**Standards and conventions:**
- "What are the naming conventions for parameters?"
- "What default worksets should I use?"
- "What are the standard line weights?"
- "What is the standard for text styles?"
- "What are the approved dimension styles?"

**Finding resources:**
- "Where can I find prevetted families?"
- "Where do I find the standard titleblocks?"
- "Where is the BBB Revit template?"

**Learning how to do something:**
- "How do I create a curtain wall in Revit?"
- "How do I set up rooms and room tags?"
- "How do I export to DWG?"
- "How do I link external files into my project?"
- "Can you walk me through how stairs and railings work?"

**Project setup:**
- "How do I set up my project browser organization?"
- "What standard door families should I use for my project?"
- "What is the process for upgrading a project?"
- "How do view templates work?"

**Families:**
- "How do I get started creating a custom Revit family?"
- "What are nested and shared families?"
- "How do formulas work in the Family Editor?"

### Suggested Prompts

Each time you start a new chat, Kodama shows three randomly chosen suggested prompts as clickable buttons. Click any of them to instantly ask that question -- a great way to explore what Kodama knows or get a quick refresher.

---

## Understanding Responses

Kodama's responses are conversational and direct -- like getting an answer from a knowledgeable colleague. Here's what you may see in a response:

- **The answer up front.** Kodama leads with the information you need rather than a lengthy preamble.
- **Source links.** When Kodama references an official standards page, PDF, or training video, it includes a clickable link so you can read the full source. Click any blue underlined link to open it in your browser.
- **Both written and video guidance together.** If there is a training video that shows the how and a standards page that defines the what, Kodama will bring both together naturally.
- **Honest "I don't know."** If the BBB standards documents do not cover your question, Kodama will tell you plainly -- for example: "I don't have that in the standards -- worth checking with your BIM Manager." It will not invent guidance.

### When Sources Conflict

The BBB SharePoint Standards Pages are always the definitive source of truth. If a training video or PDF says something different from a standards page, Kodama will defer to the standards page and may point this out.

---

## Having a Conversation

Kodama maintains context throughout your conversation, so you can ask follow-up questions naturally without restating everything.

**Example:**
> You: "What view template should I use for floor plans?"
>
> Kodama: *(answers with the standard)*
>
> You: "And what about reflected ceiling plans?"
>
> Kodama: *(understands you're still asking about view templates and answers accordingly)*

You can keep the conversation going as long as you need. Each session is saved automatically.

---

## Chat History

Every conversation you have with Kodama is saved automatically and accessible from the **sidebar** on the left side of the chat window.

**To view the sidebar:**
- Click the arrow/toggle button on the left edge of the chat window to expand it
- Your previous sessions are listed by date, titled after your first question in that session

**To return to a previous conversation:**
- Click any session in the sidebar list to load it and pick up where you left off

**To start a fresh conversation:**
- Click the **New Chat** button at the top of the sidebar (or simply open Kodama fresh)

Your chat history is stored privately on your own computer and is accessible only to you.

---

## Screenshot and Context Awareness

Kodama can be even more helpful by automatically including information about what you are currently doing in Revit when you send a question. This is enabled by default.

**Revit Context:** Kodama can see things like your current active view, what workset you're on, and what elements you have selected. This helps it give more relevant answers -- for example, if you ask "what view template should I apply?" while you have a floor plan open, Kodama already knows the view type you're working in.

**Screenshot:** Kodama can also capture a screenshot of your current Revit view and include it with your question, helping it understand what you're looking at.

Both of these features can be toggled on or off in **Settings** (the gear icon in the top right) if you prefer to keep your questions general.

---

## Executable Actions (Direct Revit Actions)

In addition to answering questions, Kodama can perform certain actions in Revit for you. When Kodama suggests a possible action, a **blue button** will appear in the chat. Clicking it performs the action immediately.

**Available actions include:**

- **Select elements** -- Find and select elements by category, parameter value, or workset
  - Example: *"Select all doors without a mark value"*
  - Example: *"Find all walls on the wrong workset"*

- **Update parameters** -- Batch-update a parameter value on your selection
  - Example: *"Update the Comments parameter to 'Verified' for my selection"*

- **Change workset** -- Move selected elements to a different workset
  - Example: *"Move these elements to the A-FURN workset"*

- **Apply view template** -- Apply a template to the active view
  - Example: *"Apply the standard floor plan view template"*

- **Isolate elements** -- Temporarily isolate selected elements in the current view
  - Example: *"Isolate these elements so I can focus on them"*

- **Check standards** -- Validate selected elements against BBB standards
  - Example: *"Check if my selection follows BBB standards"*

**How action buttons work:**

1. Ask Kodama to do something in Revit
2. A blue action button appears in the chat with a description of what will happen
3. Click the button to execute -- no additional confirmation is needed
4. The button updates to show a checkmark and a success message, or a note if something went wrong
5. You can ask follow-up questions right after an action completes

> **Note:** Actions are not available in all Revit configurations. If the blue buttons do not appear for you, contact the DCT Team.

---

## Personalizing Kodama

Open the **Settings** window (gear icon, top-right of the chat window) to personalize your experience.

**Display Name and Team:**
- Set how Kodama addresses you in the welcome message
- Add your team name for your own reference

**Custom Avatar:**
- Choose a custom avatar image that appears on your chat messages (your side of the conversation)
- Pre-loaded options are available from a dropdown; select one to preview it before saving

**Feature Toggles:**
- **Include Screenshot** -- Turn off if you do not want Kodama to capture a screenshot of Revit with each question
- **Include Context** -- Turn off if you prefer Kodama not to read your active view/selection
- **Enable Actions** -- Turn off to hide the executable action buttons and use Kodama in read-only mode

Changes take effect immediately after saving. You can return to Settings at any time to adjust.

---

## Keyboard Shortcuts

| Shortcut | Action |
|---|---|
| **Ctrl+Enter** | Send message |
| **Enter** | Add a new line (does not send) |

---

## Tips for Getting the Best Results

**Be specific.** "What worksets should I use for a healthcare project?" will get a more useful answer than "tell me about worksets."

**Ask follow-ups.** If the first answer doesn't fully address your question, just ask a follow-up. Kodama remembers the context of your conversation.

**Use it for learning.** Asking Kodama "Can you walk me through how to set up sheets for printing?" is a great way to learn a workflow step by step, with both written guidance and links to relevant training videos.

**Trust the sources.** When Kodama includes a clickable link to a standards page or training video, those links go directly to the official BBB content on SharePoint. The content there is the authoritative version.

**Ask about conflicts.** If something looks inconsistent or you think two standards might overlap, ask Kodama directly -- for example, "Does the naming convention for views apply to 3D views as well?"

**Don't worry about phrasing.** You do not need to phrase questions in any particular way. Plain, conversational language works just fine.

---

## What Kodama Does Not Do

- **Kodama does not make changes to your project on its own** (unless you click an action button)
- **Kodama does not know about your specific project** unless you describe it in your message or have context sharing enabled
- **Kodama cannot browse the internet** or find information outside of BBB's indexed standards content
- **Kodama does not replace your BIM Manager.** For questions that require project-specific judgment or decisions not covered in the standards, your BIM Manager is still the right person to ask

---

## Frequently Asked Questions

**Can I use Kodama with any Revit project?**
Yes. Kodama works in any Revit project or family file. It does not require any special project setup.

**Does Kodama save my conversations?**
Yes, conversations are saved automatically to your local computer (in your user AppData folder). They are only visible to you and are not shared with anyone else.

**How does Kodama know the BBB standards?**
Kodama searches an indexed library of BBB's standards content from SharePoint -- including standards pages, PDF guides, and training video transcripts -- and uses that content to answer your questions. It does not make up answers; it draws directly from the official documents.

**Is Kodama connected to the internet?**
Kodama connects to BBB's SharePoint (to retrieve standards documents) and to Anthropic's API (the AI service that powers the conversation). Your questions and the relevant documents are sent to Anthropic to generate a response. Anthropic's terms of service and data policy apply to that interaction.

**What if Kodama gives me wrong information?**
Kodama is powered by AI and, while it is accurate for BBB-specific questions when the standards documents are clear, it can occasionally misinterpret a question or provide incomplete information. Always apply professional judgment, and for anything business-critical, verify against the linked source documents or check with your BIM Manager.

**What if I find a gap in the standards -- something Kodama can't answer?**
If Kodama doesn't have an answer because the standards haven't been documented yet, that is valuable feedback for the BIM team. Contact the DCT Team or your BIM Manager so the gap can be addressed.

---

## Getting Help and Reporting Issues

If Kodama is not behaving as expected, or if you have feedback or a feature request, contact the **BBB DCT Team** at:
- Submit a ticket via the DCT portal: [DCT Help Desk](https://portal.bbbarch.com/a/tickets/new)

The DCT Team is responsible for maintaining and improving Kodama.

---

*Kodama is an internal tool developed by the BBB Design and Construction Technology (DCT) Team.*
*For technical documentation, see the developer README.*

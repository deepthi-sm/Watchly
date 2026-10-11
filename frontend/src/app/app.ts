import { AfterViewInit, Component, computed, effect, inject, signal } from '@angular/core';
import { DOCUMENT } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { AuthService } from './core/auth/auth.service';
import { ApiProfile, ApiThread, ApiWatchlistItem, WatchlyApiService } from './core/api/watchly-api.service';

type Tab = 'chat' | 'watchlist' | 'how';
type Filter = 'all' | 'to_watch' | 'watched';
interface WatchItem extends ApiWatchlistItem { year?: string; type?: string; color: string; }
interface Thread extends ApiThread { preview: string; time: string; }
interface ChatMessage { role: 'user' | 'assistant'; content: string; }

@Component({ selector: 'app-root', imports: [FormsModule], templateUrl: './app.html', styleUrl: './app.scss' })
export class App implements AfterViewInit {
  protected readonly auth = inject(AuthService);
  private readonly api = inject(WatchlyApiService);
  protected readonly signedIn = computed(() => !!this.auth.user());
  protected readonly displayName = computed(() => this.auth.user()?.email?.split('@')[0] || 'Movie fan');
  protected readonly initials = computed(() => this.auth.user()?.email?.slice(0, 2).toUpperCase() || 'ME');
  protected authMode = signal<'login' | 'signup'>('login');
  protected email = '';
  protected password = '';
  protected authError = signal('');
  protected authSubmitting = signal(false);
  protected activeTab = signal<Tab>('chat');
  protected activeThread = signal('');
  protected composer = '';
  protected filter = signal<Filter>('all');
  protected threadMenuOpen = signal(false);
  protected readonly threads = signal<Thread[]>([]);
  protected readonly watchlist = signal<WatchItem[]>([]);
  protected readonly chatMessages = signal<ChatMessage[]>([]);
  protected readonly trimStats = signal({ messages_before: 0, messages_sent: 0, tokens_before: 0, tokens_sent: 0, token_budget: 1200 });
  protected readonly profile = signal<ApiProfile>({});
  protected readonly graphDiagram = signal('Loading graph...');
  private readonly document = inject(DOCUMENT);
  protected readonly filteredWatchlist = computed(() => this.watchlist().filter(item => this.filter() === 'all' || item.status === this.filter()));
  protected readonly watchedCount = computed(() => this.watchlist().filter(item => item.status === 'watched').length);
  protected readonly currentThreadTitle = computed(() => this.threads().find(thread => thread.id === this.activeThread())?.title ?? (this.activeThread() ? 'Movie chat' : 'New movie chat'));
  constructor() { effect(() => { if (this.signedIn()) void this.loadLiveData(); this.chatMessages(); queueMicrotask(() => this.scrollChatToBottom()); }); }
  ngAfterViewInit(): void { this.scrollChatToBottom(); }
  private scrollChatToBottom(): void { const panel = this.document.querySelector<HTMLElement>('.messages'); panel?.scrollTo({ top: panel.scrollHeight, behavior: 'smooth' }); }
  protected selectTab(tab: Tab): void { this.activeTab.set(tab); }
  protected setFilter(filter: Filter): void { this.filter.set(filter); }
  protected formatMessage(message: ChatMessage): string {
    if (message.role === 'user') return message.content;
    return this.formatAssistant(message.content);
  }
  private formatAssistant(content: string): string {
    return content
      .replace(/\r/g, '')
      .replace(/\*\*/g, '')
      .replace(/\*/g, '')
      .replace(/\s+(?=\d+\.\s)/g, '\n\n')
      .replace(/\s+(?=(?:Sub-genre|Premise|Why watch):)/g, '\n')
      .replace(/\s+(?=Let me know)/g, '\n\n')
      .replace(/[ \t]+\n/g, '\n')
      .trim();
  }
  protected async selectThread(id: string): Promise<void> { this.activeThread.set(id); this.threadMenuOpen.set(false); const messages = await this.api.threadMessages(id); this.chatMessages.set(messages.map(message => message.role === 'assistant' ? { ...message, content: this.formatAssistant(message.content) } : message)); }
  protected async newThread(): Promise<void> { const thread = await this.api.createThread(); this.threads.update(items => [{ ...thread, preview: 'Ready when you are', time: 'now' }, ...items]); this.activeThread.set(thread.id); this.chatMessages.set([]); this.threadMenuOpen.set(false); }
  protected async toggleWatched(id: string): Promise<void> { const item = this.watchlist().find(value => value.id === id); if (!item) return; const updated = await this.api.updateWatchlist(id, item.status === 'watched' ? 'to_watch' : 'watched'); this.watchlist.update(items => items.map(value => value.id === id ? { ...value, ...updated } : value)); }
  protected async sendMessage(): Promise<void> { const message = this.composer.trim(); if (!message) return; if (!this.activeThread()) await this.newThread(); this.composer = ''; this.chatMessages.update(items => [...items, { role: 'user', content: message }]); const result = await this.api.sendMessage(this.activeThread(), message); this.chatMessages.update(items => [...items, { role: 'assistant', content: this.formatAssistant(result.reply) }]); this.trimStats.set({ ...this.trimStats(), ...result.trimStats }); this.profile.set(result.profile ?? this.profile()); this.watchlist.set(result.watchlist.map((item, index) => ({ ...item, color: ['#f4b8ca', '#ffcb71', '#b4c9ef'][index % 3] }))); }
  private async loadLiveData(): Promise<void> { try { const [threads, watchlist, memory, diagram] = await Promise.all([this.api.threads(), this.api.watchlist(), this.api.memory(), this.api.graphDiagram()]); if (!this.activeThread()) { this.threads.set(threads.map(thread => ({ ...thread, preview: 'Open chat', time: 'saved' }))); if (threads[0]) await this.selectThread(threads[0].id); } this.watchlist.set(watchlist.map((item, index) => ({ ...item, color: ['#f4b8ca', '#ffcb71', '#b4c9ef'][index % 3] }))); this.profile.set(memory.profile); this.graphDiagram.set(diagram.mermaid); } catch { /* API may still be starting; buttons will retry. */ } }
  protected async submitAuth(): Promise<void> {
    this.authError.set('');
    this.authSubmitting.set(true);
    try {
      if (this.authMode() === 'login') await this.auth.login(this.email, this.password);
      else await this.auth.signup(this.email, this.password);
    } catch (error: unknown) {
      this.authError.set(this.readableAuthError(error));
    } finally {
      this.authSubmitting.set(false);
    }
  }
  protected async logout(): Promise<void> { await this.auth.logout(); }
  private readableAuthError(error: unknown): string {
    const code = (error as { code?: string }).code;
    const messages: Record<string, string> = {
      'auth/invalid-credential': 'That email or password is not correct.',
      'auth/email-already-in-use': 'An account already exists for this email.',
      'auth/weak-password': 'Use a password with at least 6 characters.',
      'auth/invalid-email': 'Please enter a valid email address.',
      'auth/too-many-requests': 'Too many attempts. Please try again shortly.'
    };
    return messages[code ?? ''] ?? 'Unable to sign in right now. Please try again.';
  }
}

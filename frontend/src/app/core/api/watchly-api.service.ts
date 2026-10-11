import { Injectable } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { firstValueFrom } from 'rxjs';

export interface ApiThread { id: string; title: string; }
export interface ApiWatchlistItem { id: string; title: string; media_type: string; status: 'to_watch' | 'watched'; poster_path?: string; }
export interface ApiChatResponse { reply: string; trimStats: { messages_before: number; messages_sent: number; tokens_before: number; tokens_sent: number; token_budget: number }; intent: string; watchlist: ApiWatchlistItem[]; profile: ApiProfile; }
export interface ApiProfile { favorite_genre?: string; preferred_platform?: string; }

@Injectable({ providedIn: 'root' })
export class WatchlyApiService {
  private readonly baseUrl = 'http://127.0.0.1:8000';
  constructor(private readonly http: HttpClient) {}
  threads() { return firstValueFrom(this.http.get<ApiThread[]>(`${this.baseUrl}/threads`)); }
  createThread() { return firstValueFrom(this.http.post<ApiThread>(`${this.baseUrl}/threads`, {})); }
  watchlist() { return firstValueFrom(this.http.get<ApiWatchlistItem[]>(`${this.baseUrl}/watchlist`)); }
  sendMessage(threadId: string, message: string) { return firstValueFrom(this.http.post<ApiChatResponse>(`${this.baseUrl}/chat/message`, { thread_id: threadId, message })); }
    threadMessages(threadId: string) { return firstValueFrom(this.http.get<{ role: 'user' | 'assistant'; content: string }[]>(`${this.baseUrl}/threads/${threadId}/messages`)); }
    memory() { return firstValueFrom(this.http.get<{ profile: ApiProfile; shortTerm: string; longTerm: string }>(`${this.baseUrl}/memory`)); }
    graphDiagram() { return firstValueFrom(this.http.get<{ mermaid: string }>(`${this.baseUrl}/graph/diagram`)); }
  addWatchlist(title: string) { return firstValueFrom(this.http.post<ApiWatchlistItem>(`${this.baseUrl}/watchlist`, { title })); }
  updateWatchlist(itemId: string, status: 'to_watch' | 'watched') { return firstValueFrom(this.http.patch<ApiWatchlistItem>(`${this.baseUrl}/watchlist/${itemId}`, { status })); }
}

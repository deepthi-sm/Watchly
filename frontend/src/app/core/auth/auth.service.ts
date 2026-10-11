import { Injectable, signal } from '@angular/core';
import { initializeApp } from 'firebase/app';
import {
  Auth,
  User,
  createUserWithEmailAndPassword,
  getAuth,
  onAuthStateChanged,
  signInWithEmailAndPassword,
  signOut
} from 'firebase/auth';
import { firebaseConfig } from '../firebase.config';

@Injectable({ providedIn: 'root' })
export class AuthService {
  private readonly auth: Auth = getAuth(initializeApp(firebaseConfig));
  readonly user = signal<User | null>(null);
  readonly loading = signal(true);

  constructor() {
    onAuthStateChanged(this.auth, user => {
      this.user.set(user);
      this.loading.set(false);
    });
  }

  async login(email: string, password: string): Promise<void> {
    await signInWithEmailAndPassword(this.auth, email, password);
  }

  async signup(email: string, password: string): Promise<void> {
    await createUserWithEmailAndPassword(this.auth, email, password);
  }

  async logout(): Promise<void> {
    if (this.user()?.uid === 'local-demo-user') {
      this.user.set(null);
      return;
    }
    await signOut(this.auth);
  }

  useDemo(): void {
    this.user.set({ uid: 'local-demo-user', email: 'demo@watchly.local' } as User);
  }

  async idToken(): Promise<string | null> {
    return this.auth.currentUser ? this.auth.currentUser.getIdToken() : null;
  }
}

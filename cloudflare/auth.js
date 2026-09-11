import { SignJWT, jwtVerify } from 'jose';
import { clean, fail, required, decodeRow } from './database.js';

const encoder = new TextEncoder();
function decodeBase64(text) {
  const normalized = text.replaceAll('.', '+').replaceAll('-', '+').replaceAll('_', '/');
  return Uint8Array.from(atob(normalized.padEnd(Math.ceil(normalized.length / 4) * 4, '=')), x => x.charCodeAt(0));
}
function encodeBase64(bytes) { return btoa(String.fromCharCode(...bytes)).replaceAll('+', '.').replaceAll('=', ''); }
async function derive(password, salt, iterations) {
  const key = await crypto.subtle.importKey('raw', encoder.encode(password), 'PBKDF2', false, ['deriveBits']);
  return new Uint8Array(await crypto.subtle.deriveBits({ name: 'PBKDF2', salt, iterations, hash: 'SHA-256' }, key, 256));
}
export async function hashPassword(password) {
  required(password, '密码', 256);
  const salt = crypto.getRandomValues(new Uint8Array(16));
  const iterations = 100000;
  const hash = await derive(password, salt, iterations);
  // passlib compatible: a cloud backup can log in directly after restoring on NAS.
  return `$pbkdf2-sha256$${iterations}$${encodeBase64(salt)}$${encodeBase64(hash)}`;
}
export async function verifyPassword(password, encoded) {
  try {
    const [, scheme, rounds, saltText, hashText] = encoded.split('$');
    const iterations = Number(rounds);
    if (scheme !== 'pbkdf2-sha256' || iterations < 1 || iterations > 1000000) return false;
    const expected = decodeBase64(hashText);
    const actual = await derive(password, decodeBase64(saltText), iterations);
    if (actual.length !== expected.length) return false;
    let different = 0;
    for (let i = 0; i < actual.length; i++) different |= actual[i] ^ expected[i];
    return different === 0;
  } catch { return false; }
}
function secret(env) {
  if (!env.SECRET_KEY || env.SECRET_KEY.length < 32 || env.SECRET_KEY === 'yuanpeng-lab-mouse-secret-key-2026') fail(503, '服务尚未配置安全密钥');
  return encoder.encode(env.SECRET_KEY);
}
export function publicUser(user) {
  const { hashed_password, ...result } = user;
  return { ...result, is_active: Boolean(result.is_active) };
}
export async function login(db, env, data) {
  const username = required(data.username, '用户名', 64);
  const password = required(data.password, '密码', 256);
  const user = await db.prepare('SELECT * FROM users WHERE lower(username)=lower(?)').bind(username).first();
  // Do comparable password work for an unknown account; never reset default passwords.
  const fallback = '$pbkdf2-sha256$29000$AAAAAAAAAAAAAAAAAAAAAA$AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA';
  const valid = await verifyPassword(password, user?.hashed_password || fallback);
  if (!user || !user.is_active || !valid) fail(401, '用户名或密码错误');
  const access_token = await new SignJWT({ role: user.role }).setProtectedHeader({ alg: 'HS256' }).setSubject(user.username).setIssuedAt().setExpirationTime('30d').sign(secret(env));
  return { access_token, token_type: 'bearer', user: publicUser(user) };
}
export async function authenticate(request, db, env) {
  const token = request.headers.get('Authorization')?.match(/^Bearer (.+)$/i)?.[1];
  if (!token) fail(401, '系统数据受保护，请先登录账号后再查看');
  let payload;
  try { ({ payload } = await jwtVerify(token, secret(env), { algorithms: ['HS256'] })); }
  catch (error) { if (error.status === 503) throw error; fail(401, '登录已过期，请重新登录'); }
  const user = await db.prepare('SELECT * FROM users WHERE username=? AND is_active=1').bind(payload.sub).first();
  if (!user) fail(401, '登录已失效，请重新登录');
  return decodeRow('users', user);
}
export function admin(user) { if (user.role !== 'admin') fail(403, '权限不足，仅管理员可执行该操作'); }

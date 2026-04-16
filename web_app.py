from __future__ import annotations

import ast
import cgi
import json
import mimetypes
import os
import re
import asyncio
import shutil
import subprocess
import sys
import threading
import time
import uuid
from dataclasses import dataclass, field
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Callable
from urllib.parse import parse_qs, urlparse

import video_pipeline as pipeline_script


pipeline_script.load_local_env()

BASE_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = BASE_DIR / "web_runs"
DEFAULT_GEMINI_TEXT_MODELS = [
    "gemini-2.5-flash",
    "gemini-2.0-flash",
    "gemini-1.5-flash",
    "gemini-1.5-pro",
]


HTML_PAGE = """<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>AI 短视频生成平台</title>
  <style>
    :root {
      --bg: #050711;
      --bg-2: #071528;
      --bg-3: #0b2332;
      --panel: rgba(13, 23, 44, 0.56);
      --panel-2: rgba(20, 34, 58, 0.46);
      --panel-3: rgba(9, 15, 29, 0.82);
      --text: #f3f8ff;
      --muted: #9aa9c8;
      --accent: #88f7ff;
      --accent-2: #92ffd1;
      --accent-3: #b5a7ff;
      --danger: #ff8d93;
      --warning: #ffd47c;
      --border: rgba(212, 233, 255, 0.18);
      --glass-line: rgba(255, 255, 255, 0.26);
      --glow: 0 0 0 1px rgba(212,233,255,0.13), 0 28px 90px rgba(1, 8, 28, 0.5);
      --shadow: 0 28px 90px rgba(0,0,0,0.42);
      --ocean-photo: url("https://images.unsplash.com/photo-1507525428034-b723cf961d3e?auto=format&fit=crop&w=2400&q=85");
    }
    * { box-sizing: border-box; }
    body {
      margin: 0;
      color: var(--text);
      background:
        radial-gradient(circle at 12% 12%, rgba(136,247,255,0.22), transparent 22%),
        radial-gradient(circle at 86% 8%, rgba(181,167,255,0.24), transparent 25%),
        radial-gradient(circle at 70% 90%, rgba(146,255,209,0.16), transparent 28%),
        linear-gradient(145deg, var(--bg) 0%, var(--bg-2) 52%, var(--bg-3) 100%);
      font-family: "Avenir Next", "PingFang SC", "Noto Sans SC", sans-serif;
      min-height: 100vh;
      position: relative;
      overflow-x: hidden;
    }
    body::before {
      content: "";
      position: fixed;
      inset: -20%;
      background-image:
        linear-gradient(115deg, transparent 12%, rgba(255,255,255,0.14) 36%, rgba(136,247,255,0.08) 48%, transparent 66%),
        radial-gradient(circle at 18% 24%, rgba(136,247,255,0.20), transparent 16%),
        radial-gradient(circle at 72% 18%, rgba(181,167,255,0.16), transparent 18%),
        radial-gradient(circle at 54% 74%, rgba(146,255,209,0.14), transparent 17%);
      filter: blur(36px) saturate(140%);
      pointer-events: none;
      opacity: 0.58;
      mix-blend-mode: screen;
      animation: liquidDrift 14s ease-in-out infinite alternate;
    }
    body::after {
      content: "";
      position: fixed;
      inset: 0;
      background-image:
        radial-gradient(circle at 50% 0%, rgba(255,255,255,0.10), transparent 38%),
        linear-gradient(180deg, rgba(3,7,18,0.18), rgba(3,7,18,0.72) 70%, rgba(3,7,18,0.9));
      pointer-events: none;
      opacity: 0.82;
      z-index: 1;
    }
    .ocean-video {
      position: fixed;
      inset: 0;
      width: 100%;
      height: 100%;
      object-fit: cover;
      z-index: 0;
      pointer-events: none;
      opacity: 1;
      background: var(--ocean-photo) center / cover no-repeat;
      filter: saturate(112%) contrast(106%) brightness(0.72);
      animation: oceanPhotoPan 28s ease-in-out infinite alternate;
      will-change: transform, filter;
    }
    @keyframes liquidDrift {
      0% { transform: translate3d(-2%, -1%, 0) scale(1); }
      50% { transform: translate3d(2%, 1.5%, 0) scale(1.05) rotate(2deg); }
      100% { transform: translate3d(-1%, 3%, 0) scale(1.02) rotate(-2deg); }
    }
    @keyframes oceanPhotoPan {
      0% { transform: scale(1.04) translate3d(-1.2%, -0.8%, 0); filter: saturate(108%) contrast(104%) brightness(0.76); }
      50% { transform: scale(1.08) translate3d(1.4%, 0.9%, 0); filter: saturate(116%) contrast(108%) brightness(0.82); }
      100% { transform: scale(1.05) translate3d(-0.4%, 1.5%, 0); filter: saturate(112%) contrast(106%) brightness(0.78); }
    }
    @keyframes auroraSweep {
      0% { transform: translateX(-45%) rotate(8deg); opacity: 0.42; }
      50% { opacity: 0.78; }
      100% { transform: translateX(35%) rotate(8deg); opacity: 0.48; }
    }
    @keyframes cardFloat {
      0%, 100% { transform: translateY(0); }
      50% { transform: translateY(-2px); }
    }
    .shell {
      max-width: 1560px;
      margin: 0 auto;
      padding: 12px 16px 20px;
      position: relative;
      z-index: 2;
    }
    .hero {
      margin-bottom: 10px;
      padding: 14px 16px;
      border: 1px solid var(--border);
      background:
        linear-gradient(135deg, rgba(255,255,255,0.2), rgba(255,255,255,0.055) 42%, rgba(136,247,255,0.08)),
        linear-gradient(180deg, rgba(12,25,46,0.66), rgba(10,17,32,0.46));
      backdrop-filter: blur(28px) saturate(150%);
      -webkit-backdrop-filter: blur(28px) saturate(150%);
      border-radius: 28px;
      box-shadow: var(--glow);
      position: relative;
      overflow: hidden;
    }
    .hero::before {
      content: "";
      position: absolute;
      inset: -120% auto auto -40%;
      width: 72%;
      height: 320%;
      background: linear-gradient(90deg, transparent, rgba(255,255,255,0.22), transparent);
      filter: blur(18px);
      pointer-events: none;
      animation: auroraSweep 10s ease-in-out infinite alternate;
    }
    .hero::after {
      content: "";
      position: absolute;
      inset: auto -10% -55% 35%;
      height: 220px;
      background: radial-gradient(circle, rgba(136,247,255,0.26), transparent 60%);
      filter: blur(34px);
      pointer-events: none;
    }
    .hero h1 {
      margin: 0 0 8px;
      font-size: 24px;
      letter-spacing: 0.02em;
      font-weight: 700;
    }
    .hero p {
      margin: 0;
      color: var(--muted);
      line-height: 1.55;
      font-size: 13px;
      max-width: 760px;
    }
    .hero-grid {
      display: grid;
      grid-template-columns: minmax(0, 1.2fr) minmax(280px, 0.8fr);
      gap: 14px;
      align-items: start;
      position: relative;
      z-index: 1;
    }
    .hero-kickers {
      display: flex;
      gap: 8px;
      flex-wrap: wrap;
      margin-bottom: 10px;
    }
    .kicker {
      display: inline-flex;
      align-items: center;
      gap: 8px;
      padding: 6px 10px;
      border-radius: 999px;
      border: 1px solid rgba(110,242,255,0.22);
      background: rgba(110,242,255,0.08);
      color: #c8faff;
      font-size: 10px;
      letter-spacing: 0.06em;
      text-transform: uppercase;
    }
    .hero-metrics {
      display: grid;
      grid-template-columns: repeat(2, minmax(0, 1fr));
      gap: 8px;
    }
    .metric {
      padding: 10px 12px;
      border-radius: 16px;
      background:
        linear-gradient(160deg, rgba(255,255,255,0.12), rgba(255,255,255,0.035)),
        rgba(11,22,42,0.44);
      border: 1px solid rgba(255, 255, 255, 0.14);
      box-shadow: inset 0 1px 0 rgba(255,255,255,0.18), 0 14px 34px rgba(0,0,0,0.16);
      backdrop-filter: blur(18px);
      -webkit-backdrop-filter: blur(18px);
    }
    .metric strong {
      display: block;
      font-size: 16px;
      color: #ffffff;
      margin-bottom: 2px;
    }
    .metric span {
      color: var(--muted);
      font-size: 11px;
      line-height: 1.4;
    }
    .layout {
      display: grid;
      grid-template-columns: minmax(0, 1.5fr) minmax(380px, 0.9fr);
      gap: 16px;
      align-items: start;
    }
    .panel {
      background:
        linear-gradient(145deg, rgba(255,255,255,0.13), rgba(255,255,255,0.036) 34%, rgba(136,247,255,0.035)),
        var(--panel);
      border: 1px solid var(--border);
      border-radius: 28px;
      box-shadow: var(--glow);
      overflow: hidden;
      backdrop-filter: blur(30px) saturate(150%);
      -webkit-backdrop-filter: blur(30px) saturate(150%);
      position: relative;
    }
    .panel::before {
      content: "";
      position: absolute;
      inset: 1px;
      border-radius: 27px;
      pointer-events: none;
      background:
        linear-gradient(132deg, rgba(255,255,255,0.22), transparent 28%, rgba(136,247,255,0.06) 52%, transparent 72%),
        radial-gradient(circle at 14% 0%, rgba(136,247,255,0.14), transparent 28%);
      opacity: 0.76;
      mix-blend-mode: screen;
    }
    .panel::after {
      content: "";
      position: absolute;
      inset: 0;
      pointer-events: none;
      border-radius: inherit;
      background:
        radial-gradient(120px 80px at 18% 8%, rgba(255,255,255,0.16), transparent 58%),
        radial-gradient(180px 120px at 92% 4%, rgba(136,247,255,0.10), transparent 58%);
      opacity: 0.74;
    }
    .panel > * {
      position: relative;
      z-index: 1;
    }
    .create-panel .panel-body {
      max-height: calc(100vh - 176px);
      overflow: auto;
      padding-bottom: 110px;
    }
    .side-panel {
      position: sticky;
      top: 14px;
    }
    .side-panel .panel-body {
      max-height: calc(100vh - 96px);
      overflow: auto;
    }
    .panel-head {
      display: flex;
      justify-content: space-between;
      align-items: center;
      padding: 16px 18px 12px;
      border-bottom: 1px solid rgba(151,184,255,0.08);
      position: sticky;
      top: 0;
      z-index: 3;
      background: rgba(8, 14, 32, 0.58);
      backdrop-filter: blur(22px) saturate(140%);
      -webkit-backdrop-filter: blur(22px) saturate(140%);
    }
    .panel-head h2 {
      margin: 0;
      font-size: 16px;
      letter-spacing: 0.03em;
    }
    .panel-body {
      padding: 0 18px 18px;
    }
    .grid {
      display: grid;
      grid-template-columns: repeat(2, minmax(0, 1fr));
      gap: 10px;
    }
    .form-section {
      grid-column: 1 / -1;
      padding: 14px;
      border-radius: 22px;
      border: 1px solid rgba(255,255,255,0.12);
      background:
        linear-gradient(145deg, rgba(255,255,255,0.09), rgba(255,255,255,0.026)),
        rgba(12, 22, 42, 0.34);
      box-shadow: inset 0 1px 0 rgba(255,255,255,0.08), 0 16px 38px rgba(0,0,0,0.12);
      backdrop-filter: blur(18px);
      -webkit-backdrop-filter: blur(18px);
      margin-bottom: 4px;
      scroll-margin-top: 160px;
      transition: border-color .2s ease, background .2s ease, transform .2s ease;
    }
    .form-section:hover {
      border-color: rgba(136,247,255,0.24);
      transform: translateY(-1px);
    }
    .form-section h3 {
      margin: 0 0 14px;
      font-size: 13px;
      letter-spacing: 0.08em;
      text-transform: uppercase;
      color: #d7e4ff;
    }
    .section-intro {
      margin: -4px 0 10px;
      color: var(--muted);
      font-size: 11px;
      line-height: 1.5;
    }
    .section-grid {
      display: grid;
      grid-template-columns: repeat(2, minmax(0, 1fr));
      gap: 10px;
    }
    .field {
      display: flex;
      flex-direction: column;
      gap: 6px;
      margin-bottom: 10px;
    }
    .field.full { grid-column: 1 / -1; }
    .conditional-group {
      grid-column: 1 / -1;
      display: grid;
      grid-template-columns: repeat(2, minmax(0, 1fr));
      gap: 14px;
    }
    .is-hidden {
      display: none !important;
    }
    label {
      font-size: 12px;
      color: var(--muted);
      letter-spacing: 0.02em;
    }
    input, textarea, select {
      width: 100%;
      border: 1px solid rgba(151,184,255,0.12);
      background:
        linear-gradient(180deg, rgba(255,255,255,0.095), rgba(255,255,255,0.028)),
        var(--panel-2);
      color: var(--text);
      border-radius: 14px;
      padding: 10px 12px;
      font-size: 13px;
      outline: none;
      transition: border-color .2s ease, box-shadow .2s ease, transform .2s ease;
      backdrop-filter: blur(16px);
      -webkit-backdrop-filter: blur(16px);
    }
    textarea {
      min-height: 150px;
      resize: vertical;
      line-height: 1.6;
    }
    input:focus, textarea:focus, select:focus {
      border-color: rgba(110,242,255,0.65);
      box-shadow: 0 0 0 3px rgba(110,242,255,0.14), 0 0 24px rgba(110,242,255,0.12);
      transform: translateY(-1px);
    }
    .inline {
      display: flex;
      gap: 12px;
      align-items: center;
      flex-wrap: wrap;
    }
    .inline label { margin-right: 6px; }
    .checkbox {
      display: flex;
      align-items: center;
      gap: 10px;
      color: var(--text);
    }
    .checkbox input {
      width: auto;
      margin: 0;
    }
    .actions {
      display: flex;
      gap: 10px;
      flex-wrap: wrap;
      margin-top: 6px;
    }
    .submit-bar {
      position: static;
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 16px;
      margin-top: 12px;
      padding: 10px 12px;
      border: 1px solid rgba(151,184,255,0.12);
      border-radius: 20px;
      background:
        linear-gradient(135deg, rgba(255,255,255,0.11), rgba(255,255,255,0.035)),
        rgba(8, 16, 32, 0.44);
      backdrop-filter: blur(18px) saturate(145%);
      -webkit-backdrop-filter: blur(18px) saturate(145%);
      box-shadow: inset 0 1px 0 rgba(255,255,255,0.1);
    }
    .submit-copy {
      color: var(--muted);
      font-size: 11px;
      line-height: 1.5;
    }
    .quick-status {
      display: flex;
      gap: 6px;
      flex-wrap: wrap;
      margin-top: 10px;
    }
    .status-pill {
      display: inline-flex;
      align-items: center;
      gap: 8px;
      padding: 7px 10px;
      border-radius: 999px;
      font-size: 11px;
      border: 1px solid rgba(151,184,255,0.12);
      background: rgba(255,255,255,0.04);
      color: var(--muted);
      backdrop-filter: blur(14px);
      -webkit-backdrop-filter: blur(14px);
    }
    .status-pill.ok {
      color: #cffff0;
      border-color: rgba(102,255,179,0.24);
      background: rgba(102,255,179,0.08);
    }
    .status-pill.warn {
      color: #ffe4b2;
      border-color: rgba(255,199,110,0.24);
      background: rgba(255,199,110,0.08);
    }
    .style-pills {
      display: flex;
      gap: 8px;
      flex-wrap: wrap;
      margin-top: 4px;
    }
    .style-pill {
      border: 1px solid rgba(151,184,255,0.14);
      background: rgba(255,255,255,0.04);
      color: var(--muted);
      border-radius: 999px;
      padding: 8px 12px;
      font-size: 12px;
      cursor: pointer;
      transition: border-color .2s ease, background .2s ease, color .2s ease;
    }
    .style-pill.active {
      color: #06131d;
      background: linear-gradient(135deg, var(--accent), var(--accent-2));
      border-color: transparent;
      box-shadow: 0 8px 20px rgba(110,242,255,0.16);
    }
    .voice-note {
      color: var(--muted);
      font-size: 12px;
      line-height: 1.6;
      margin-top: 6px;
    }
    button {
      border: 0;
      border-radius: 999px;
      padding: 12px 18px;
      font-size: 14px;
      font-weight: 600;
      cursor: pointer;
      transition: transform .18s ease, opacity .18s ease, box-shadow .18s ease, filter .18s ease;
      position: relative;
      overflow: hidden;
    }
    button::after {
      content: "";
      position: absolute;
      inset: 0;
      background: linear-gradient(110deg, transparent 0%, rgba(255,255,255,0.24) 45%, transparent 70%);
      transform: translateX(-120%);
      transition: transform .55s ease;
      pointer-events: none;
    }
    button:hover {
      transform: translateY(-1px);
      filter: brightness(1.04);
    }
    button:hover::after { transform: translateX(120%); }
    .primary {
      background: linear-gradient(135deg, var(--accent), var(--accent-2));
      color: #03131b;
      box-shadow: 0 12px 34px rgba(136,247,255,0.24), inset 0 1px 0 rgba(255,255,255,0.42);
    }
    .secondary {
      background: rgba(255,255,255,0.095);
      color: var(--text);
      border: 1px solid rgba(255,255,255,0.12);
    }
    .ghost {
      background: rgba(181,167,255,0.12);
      color: #dce2ff;
      border: 1px solid rgba(181,167,255,0.2);
    }
    .candidate-toolbar {
      display: flex;
      gap: 10px;
      align-items: center;
      flex-wrap: wrap;
      margin: 6px 0 12px;
    }
    .candidate-grid {
      display: grid;
      grid-template-columns: repeat(3, minmax(0, 1fr));
      gap: 10px;
      margin-top: 10px;
    }
    .candidate-card {
      border-radius: 20px;
      border: 1px solid rgba(255,255,255,0.13);
      background:
        linear-gradient(145deg, rgba(255,255,255,0.1), rgba(255,255,255,0.03)),
        rgba(10, 20, 38, 0.38);
      overflow: hidden;
      position: relative;
      transition: transform .2s ease, border-color .2s ease, box-shadow .2s ease;
    }
    .candidate-card:hover {
      transform: translateY(-2px);
      border-color: rgba(136,247,255,0.28);
      box-shadow: 0 18px 40px rgba(0,0,0,0.22);
    }
    .candidate-card.selected {
      border-color: rgba(110,242,255,0.52);
      box-shadow: 0 0 0 1px rgba(110,242,255,0.22), 0 12px 30px rgba(0,0,0,0.22);
    }
    .candidate-thumb {
      aspect-ratio: 16 / 9;
      width: 100%;
      background: linear-gradient(135deg, rgba(125,140,255,0.22), rgba(110,242,255,0.08));
      overflow: hidden;
    }
    .candidate-thumb img,
    .candidate-thumb video {
      width: 100%;
      height: 100%;
      object-fit: cover;
      display: block;
    }
    .candidate-body {
      padding: 10px;
      display: grid;
      gap: 6px;
    }
    .candidate-body strong {
      font-size: 13px;
      line-height: 1.5;
    }
    .candidate-meta {
      color: var(--muted);
      font-size: 11px;
      line-height: 1.5;
      word-break: break-word;
    }
    .candidate-actions {
      display: flex;
      gap: 8px;
    }
    .candidate-actions button {
      flex: 1;
      padding: 10px 12px;
      font-size: 12px;
    }
    .selection-chip {
      display: none;
      margin-top: 10px;
      padding: 10px 12px;
      border-radius: 14px;
      border: 1px solid rgba(102,255,179,0.18);
      background: rgba(102,255,179,0.08);
      color: #cffff0;
      font-size: 12px;
      line-height: 1.6;
    }
    .selection-chip.active {
      display: block;
    }
    .selected-strip {
      display: none;
      grid-template-columns: repeat(3, minmax(0, 1fr));
      gap: 10px;
      margin-top: 12px;
    }
    .selected-strip.active {
      display: grid;
    }
    .selected-card {
      border-radius: 18px;
      border: 1px solid rgba(255,255,255,0.13);
      background:
        linear-gradient(145deg, rgba(255,255,255,0.1), rgba(255,255,255,0.035)),
        rgba(10,20,38,0.38);
      overflow: hidden;
    }
    .selected-card .candidate-thumb {
      aspect-ratio: 16 / 9;
    }
    .selected-body {
      padding: 10px;
      display: grid;
      gap: 8px;
    }
    .selected-order {
      font-size: 11px;
      color: var(--accent);
      letter-spacing: 0.08em;
      text-transform: uppercase;
    }
    .selected-title {
      font-size: 12px;
      line-height: 1.5;
    }
    .selected-actions {
      display: flex;
      gap: 6px;
    }
    .selected-actions button {
      flex: 1;
      padding: 8px 10px;
      font-size: 12px;
    }
    .jobs {
      display: grid;
      gap: 10px;
    }
    .job {
      padding: 12px;
      border-radius: 18px;
      border: 1px solid rgba(255,255,255,0.13);
      background:
        linear-gradient(145deg, rgba(255,255,255,0.1), rgba(255,255,255,0.03)),
        rgba(10, 20, 38, 0.42);
      box-shadow: inset 0 1px 0 rgba(255,255,255,0.08), 0 14px 34px rgba(0,0,0,0.14);
      animation: cardFloat 7s ease-in-out infinite;
    }
    .job h3 {
      margin: 0 0 8px;
      font-size: 15px;
    }
    .actions-row {
      display: flex;
      gap: 8px;
      flex-wrap: wrap;
      margin-top: 12px;
    }
    .pill {
      display: inline-flex;
      align-items: center;
      justify-content: center;
      padding: 8px 12px;
      border-radius: 999px;
      text-decoration: none;
      background: rgba(255,255,255,0.08);
      color: var(--text);
      font-size: 12px;
      border: 1px solid rgba(151,184,255,0.1);
    }
    video {
      width: 100%;
      margin-top: 12px;
      border-radius: 16px;
      background: #04070f;
      border: 1px solid rgba(151,184,255,0.08);
    }
    .meta {
      font-size: 11px;
      color: var(--muted);
      line-height: 1.5;
      word-break: break-all;
    }
    .status {
      display: inline-flex;
      align-items: center;
      gap: 8px;
      border-radius: 999px;
      padding: 6px 10px;
      font-size: 12px;
      margin-bottom: 10px;
    }
    .queued, .running { background: rgba(255,199,110,0.14); color: #ffd59a; }
    .success { background: rgba(102,255,179,0.14); color: #b3ffe1; }
    .failed { background: rgba(255,141,147,0.16); color: #ffc1c4; }
    pre {
      margin: 10px 0 0;
      padding: 14px;
      border-radius: 16px;
      background: rgba(5,10,20,0.55);
      color: #d6ddf5;
      white-space: pre-wrap;
      word-break: break-word;
      font-size: 12px;
      line-height: 1.6;
      max-height: 220px;
      overflow: auto;
    }
    .tip {
      color: var(--muted);
      font-size: 12px;
      line-height: 1.6;
    }
    .toast {
      position: fixed;
      right: 22px;
      top: 22px;
      z-index: 50;
      max-width: min(360px, calc(100vw - 44px));
      padding: 14px 16px;
      border-radius: 18px;
      border: 1px solid rgba(110,242,255,0.28);
      background:
        linear-gradient(135deg, rgba(110,242,255,0.18), rgba(102,255,179,0.10)),
        rgba(8, 14, 32, 0.94);
      color: var(--text);
      box-shadow: var(--shadow);
      opacity: 0;
      transform: translateY(-12px);
      pointer-events: none;
      transition: opacity .2s ease, transform .2s ease;
      line-height: 1.6;
      font-size: 13px;
    }
    .toast.show {
      opacity: 1;
      transform: translateY(0);
    }
    @media (max-width: 960px) {
      .shell { padding-left: 20px; }
      .layout { grid-template-columns: 1fr; }
      .create-panel .panel-body,
      .side-panel .panel-body { max-height: none; overflow: visible; }
      .side-panel { position: static; }
      .grid { grid-template-columns: 1fr; }
      .section-grid { grid-template-columns: 1fr; }
      .hero h1 { font-size: 28px; }
      .hero-grid { grid-template-columns: 1fr; }
      .candidate-grid { grid-template-columns: 1fr; }
      .selected-strip { grid-template-columns: 1fr; }
      .submit-bar { flex-direction: column; align-items: stretch; }
      .conditional-group { grid-template-columns: 1fr; }
    }
    @media (prefers-reduced-motion: reduce) {
      *, *::before, *::after {
        animation-duration: 0.001ms !important;
        animation-iteration-count: 1 !important;
        scroll-behavior: auto !important;
        transition-duration: 0.001ms !important;
      }
    }
  </style>
</head>
<body>
  <video class="ocean-video" autoplay muted loop playsinline preload="metadata" poster="https://images.unsplash.com/photo-1507525428034-b723cf961d3e?auto=format&fit=crop&w=2400&q=85" aria-hidden="true">
    <source src="https://upload.wikimedia.org/wikipedia/commons/transcoded/9/9c/Ocean_surface_waves_04.ogv/Ocean_surface_waves_04.ogv.480p.webm" type="video/webm">
  </video>
  <div id="toast" class="toast" role="status" aria-live="polite"></div>
  <div class="shell">
    <section class="hero">
      <div class="hero-grid">
        <div>
          <div class="hero-kickers">
            <span class="kicker">AI Video Lab</span>
            <span class="kicker">Storyboard + Avatar</span>
            <span class="kicker">Local Control Center</span>
          </div>
          <h1>AI 短视频生成平台</h1>
          <p>在浏览器里完成文案、背景、配音、字幕和分镜配置。系统会在本地组织生成链路、轮询任务状态，并把成片、日志和中间资产完整保存到你的工作目录里。</p>
          <div class="quick-status">
            <span id="gemini-ready-pill" class="status-pill">Gemini 未检测</span>
            <span id="pexels-ready-pill" class="status-pill">Pexels 未检测</span>
            <span id="whisper-ready-pill" class="status-pill">Whisper 模型未检测</span>
          </div>
        </div>
        <div class="hero-metrics">
          <div class="metric">
            <strong>2</strong>
            <span>生成路线：数字人口播 / 内容短视频</span>
          </div>
          <div class="metric">
            <strong>Pexels</strong>
            <span>支持候选预览、手动挑选与自动搜索</span>
          </div>
          <div class="metric">
            <strong>Auto</strong>
            <span>分段、字幕、背景与转场自动编排</span>
          </div>
          <div class="metric">
            <strong>Local</strong>
            <span>任务日志、成片与缓存素材都保存在本地</span>
          </div>
        </div>
      </div>
    </section>
    <div class="layout">
      <section class="panel create-panel">
        <div class="panel-head">
          <h2>创建任务</h2>
        </div>
        <div class="panel-body">
          <form id="job-form">
            <div class="grid">
              <section class="form-section" id="section-script">
                <h3>文案工作台</h3>
                <p class="section-intro">先写想法，再决定是懒人一键生成还是手动精修。AI 会帮你生成标题、文案、背景提示词和推荐模式。</p>
                <div class="section-grid">
                  <div class="field">
                    <label for="title">任务标题</label>
                    <input id="title" name="title" value="midnight_store_web">
                  </div>
                  <div class="field">
                    <label for="video-mode">视频模式</label>
                    <select id="video-mode" name="video_mode">
                      <option value="storyboard">内容短视频模式（无数字人）</option>
                      <option value="tencent">腾讯云数字人口播</option>
                    </select>
                  </div>
                  <div class="field full">
                    <label for="creation-mode">创作模式</label>
                    <select id="creation-mode" name="creation_mode">
                      <option value="lazy" selected>懒人模式：不挑素材，一键生成</option>
                      <option value="custom">精修模式：先挑背景素材，再生成</option>
                    </select>
                    <span class="tip">懒人模式会自动搜索并编排背景；精修模式会优先使用你在候选区选择或本地上传的素材。</span>
                  </div>
                  <div class="field full">
                    <label for="idea">你的想法</label>
                    <textarea id="idea" name="idea" style="min-height:110px" placeholder="例如：我想做一条关于深夜便利店与都市孤独感的治愈短视频"></textarea>
                  </div>
                  <div class="field">
                    <label for="gemini-model">Gemini 文案模型</label>
                    <select id="gemini-model" name="gemini_model">
                      <option value="gemini-2.5-flash" selected>gemini-2.5-flash</option>
                      <option value="gemini-2.0-flash">gemini-2.0-flash</option>
                      <option value="gemini-1.5-flash">gemini-1.5-flash</option>
                      <option value="gemini-1.5-pro">gemini-1.5-pro</option>
                    </select>
                    <span class="tip">默认推荐 `gemini-2.5-flash`。如果某个模型暂时不稳定，可以直接切换。</span>
                  </div>
                  <div class="field">
                    <label for="gemini-model-custom">自定义 Gemini 模型名</label>
                    <input id="gemini-model-custom" placeholder="例如 gemini-2.0-flash-exp；留空则使用上方选择">
                  </div>
                  <div class="field">
                    <label for="gemini-api-key">Gemini API Key</label>
                    <input id="gemini-api-key" name="gemini_api_key" placeholder="留空则自动读取 .env / GEMINI_API_KEY">
                    <span id="gemini-key-status" class="tip">正在检测本地配置...</span>
                  </div>
                  <input type="hidden" id="script-style" name="script_style" value="healing">
                  <div class="field full">
                    <div class="actions">
                      <button class="ghost" type="button" id="generate-script">AI 生成文案</button>
                      <button class="secondary" type="button" id="fill-demo">填入示例文案</button>
                    </div>
                  </div>
                  <div class="field full">
                    <label for="text">文案</label>
                    <textarea id="text" name="text" placeholder="在这里输入文案，或先用 AI 生成"></textarea>
                  </div>
                </div>
              </section>

              <section class="form-section" id="section-background">
                <h3>背景与分镜</h3>
                <p class="section-intro">懒人模式下这里可以少碰；精修模式下你可以预览候选、手动排序，或者直接上传本地背景素材。</p>
                <div class="section-grid">
                  <div class="field">
                    <label for="background-mode">背景方式</label>
                    <select id="background-mode" name="background_mode">
                      <option value="manual">手动背景图</option>
                      <option value="pexels">Pexels 背景图</option>
                      <option value="pexels-video" selected>Pexels 背景视频</option>
                      <option value="webhook">自定义接口生成背景图</option>
                      <option value="none">不替换背景</option>
                    </select>
                  </div>
                  <div class="field">
                    <label for="split-max-chars">每段最大字数</label>
                    <input id="split-max-chars" name="split_max_chars" type="number" value="120">
                  </div>
                  <div id="manual-background-group" class="conditional-group">
                    <div class="field">
                      <label for="background-image">背景图片路径</label>
                      <input id="background-image" name="background_image" placeholder="/path/to/background.jpg">
                    </div>
                    <div class="field">
                      <label for="background-video">背景视频路径</label>
                      <input id="background-video" name="background_video" placeholder="/path/to/background.mp4">
                    </div>
                    <div class="field full">
                      <label for="background-upload">本地上传背景图/视频</label>
                      <input id="background-upload" type="file" accept="image/*,video/*">
                      <div class="actions">
                        <button class="ghost" type="button" id="upload-background">上传为背景素材</button>
                      </div>
                      <span class="tip">上传后会自动切换为手动背景，并填入本地路径。</span>
                    </div>
                  </div>
                  <div id="background-prompt-group" class="field full">
                    <label for="background-prompt">背景提示词</label>
                    <textarea id="background-prompt" name="background_prompt" style="min-height:110px" placeholder="用于 Pexels 搜索或自定义接口生成背景"></textarea>
                  </div>
                  <div id="pexels-candidate-group" class="field full">
	                    <div class="candidate-toolbar">
	                      <button class="ghost" type="button" id="preview-backgrounds">预览候选背景</button>
	                      <button class="secondary" type="button" id="refresh-candidates">刷新未选候选</button>
		                      <span class="tip">先看候选，再挑选分镜序列；当前素材播完会切到下一条。</span>
	                    </div>
                    <div id="selection-chip" class="selection-chip"></div>
                    <div id="selected-strip" class="selected-strip"></div>
                    <div id="candidate-grid" class="candidate-grid"></div>
                    <input type="hidden" id="selected-background-assets" name="selected_background_assets">
                  </div>
                  <div id="webhook-background-config-group" class="field full">
                    <label for="background-config">背景生成配置文件</label>
                    <input id="background-config" name="background_config" value="__BACKGROUND_CONFIG__">
                  </div>
                  <div id="pexels-key-group" class="field full">
                    <label for="pexels-api-key">Pexels API Key</label>
                    <input id="pexels-api-key" name="pexels_api_key" placeholder="留空则自动读取 .env / PEXELS_API_KEY">
                    <span id="pexels-key-status" class="tip">正在检测本地配置...</span>
                  </div>
                  <div class="field full">
                    <div class="checkbox">
                      <input id="auto-split" name="auto_split" type="checkbox" checked>
                      <label for="auto-split">自动分段并拼接</label>
                    </div>
                  </div>
                  <div class="field full">
                    <div class="checkbox">
                      <input id="storyboard-dynamic-backgrounds" name="storyboard_dynamic_backgrounds" type="checkbox" checked>
                      <label for="storyboard-dynamic-backgrounds">内容短视频模式按分段自动换背景</label>
                    </div>
                  </div>
	                  <div class="field full">
	                    <div class="checkbox">
	                      <input id="storyboard-transitions" name="storyboard_transitions" type="checkbox" checked>
	                      <label for="storyboard-transitions">内容短视频模式添加轻微转场</label>
	                    </div>
	                  </div>
	                  <div class="field full">
	                    <div class="checkbox">
	                      <input id="fast-mode" name="fast_mode" type="checkbox" checked>
	                      <label for="fast-mode">快速预览模式（更快生成，画质略降）</label>
	                    </div>
	                  </div>
	                </div>
	              </section>

              <section class="form-section" id="section-output">
                <h3>输出与高级参数</h3>
                <p class="section-intro">这里放声音、字幕、Whisper 精准字幕、BGM 和腾讯云参数。默认值已经偏向易用，不必每次都调。</p>
                <div class="section-grid">
                  <div class="field">
                    <label for="voice">配音音色</label>
                    <div class="style-pills" id="voice-filter-group">
                      <button class="style-pill active" type="button" data-voice-filter="all">全部</button>
                      <button class="style-pill" type="button" data-voice-filter="female">女声</button>
                      <button class="style-pill" type="button" data-voice-filter="male">男声</button>
                      <button class="style-pill" type="button" data-voice-filter="dialect">方言</button>
                    </div>
                    <select id="voice" name="voice">
                      <option value="zh-CN-XiaoxiaoNeural" data-group="female" data-note="温柔自然，适合治愈系和日常口播。">晓晓 · 温柔女声</option>
                      <option value="zh-CN-XiaoyiNeural" data-group="female" data-note="更轻柔一些，适合情绪感和旁白。">晓伊 · 轻柔女声</option>
                      <option value="zh-CN-YunxiNeural" data-group="male" data-note="沉稳成熟，适合叙事和知识表达。">云希 · 沉稳男声</option>
                      <option value="zh-CN-YunjianNeural" data-group="male" data-note="更年轻利落，适合科技和效率内容。">云健 · 青年男声</option>
                      <option value="zh-CN-liaoning-XiaobeiNeural" data-group="dialect" data-note="带地域感，更有生活气和辨识度。">晓北 · 东北女声</option>
                      <option value="zh-CN-shaanxi-XiaoniNeural" data-group="dialect" data-note="风格鲜明，适合有个性的轻内容表达。">晓妮 · 陕西女声</option>
                    </select>
                    <div id="voice-note" class="voice-note">温柔自然，适合治愈系和日常口播。</div>
                    <div class="actions">
                      <button class="ghost" type="button" id="preview-voice">试听 5 秒</button>
                    </div>
                  </div>
                  <div class="field">
                    <label for="rate">语速</label>
                    <select id="rate" name="rate">
                      <option value="-10%">偏慢</option>
                      <option value="+0%" selected>正常</option>
                      <option value="+10%">偏快</option>
                      <option value="+20%">更快</option>
                    </select>
                  </div>
                  <div class="field">
                    <label for="volume">音量</label>
                    <select id="volume" name="volume">
                      <option value="-10%">偏低</option>
                      <option value="+0%" selected>正常</option>
                      <option value="+10%">偏高</option>
                      <option value="+20%">更高</option>
                    </select>
                  </div>
                  <div class="field full">
                    <div class="checkbox">
                      <input id="add-subtitles" name="add_subtitles" type="checkbox" checked>
                      <label for="add-subtitles">自动加字幕</label>
                    </div>
                  </div>
                  <div id="subtitle-settings-group" class="conditional-group">
                  <div class="field">
                    <label for="subtitle-provider">字幕模式</label>
                    <select id="subtitle-provider" name="subtitle_provider">
                      <option value="heuristic" selected>快速模式（估算时间，速度快）</option>
                      <option value="whisper">精准模式（Whisper 时间戳）</option>
                    </select>
                  </div>
                  <div class="field">
                    <label for="subtitle-max-chars">字幕每条字数</label>
                    <input id="subtitle-max-chars" name="subtitle_max_chars" type="number" value="22">
                  </div>
                  <div class="field">
                    <label for="subtitle-font-size">字幕字号</label>
                    <input id="subtitle-font-size" name="subtitle_font_size" type="number" value="18">
                  </div>
                  <div class="field">
                    <label for="subtitle-bar-height">字幕条高度</label>
                    <input id="subtitle-bar-height" name="subtitle_bar_height" type="number" value="170">
                  </div>
                  <div class="field">
                    <label for="subtitle-bar-opacity">字幕条透明度</label>
                    <input id="subtitle-bar-opacity" name="subtitle_bar_opacity" type="number" step="0.01" value="0.34">
                  </div>
                  <div class="field">
                    <label for="subtitle-offset">字幕自校对偏移（秒）</label>
                    <input id="subtitle-offset" name="subtitle_offset" type="number" step="0.05" value="-0.15">
                    <span class="tip">负数表示字幕提前。若字幕慢半拍，可试 -0.25；若太早，可试 0。</span>
                  </div>
                  </div>
                  <div id="whisper-settings-group" class="conditional-group">
                  <div class="field full">
                    <label for="whisper-model-select">检测到的 Whisper 模型</label>
                    <select id="whisper-model-select">
                      <option value="">手动输入或等待自动检测</option>
                    </select>
                    <span class="tip">会自动扫描项目 `models/` 目录和 `.env` 中的 Whisper 模型路径。</span>
                  </div>
                  <div class="field full">
                    <label for="whisper-model">Whisper 模型路径</label>
                    <input id="whisper-model" name="whisper_model" placeholder="/path/to/ggml-base.bin">
                    <span class="tip">仅在精准模式下生效。留空则读取环境变量 WHISPER_MODEL_PATH。</span>
                  </div>
                  <div class="field">
                    <label for="whisper-language">Whisper 语言</label>
                    <input id="whisper-language" name="whisper_language" value="zh">
                  </div>
                  </div>
                  <div class="field">
                    <label for="bgm-volume">BGM 音量</label>
                    <input id="bgm-volume" name="bgm_volume" type="number" step="0.01" value="0.18">
                  </div>
                  <div class="field full">
                    <label for="bgm-audio">BGM 音频路径</label>
                    <input id="bgm-audio" name="bgm_audio" placeholder="/path/to/bgm.mp3">
                  </div>
                  <div class="field full">
                    <label for="bgm-upload">本地上传 BGM</label>
                    <input id="bgm-upload" type="file" accept="audio/*">
                    <div class="actions">
                      <button class="ghost" type="button" id="upload-bgm">上传为 BGM</button>
                    </div>
                  </div>
                  <div class="field">
                    <label for="storyboard-transition-duration">转场时长</label>
                    <input id="storyboard-transition-duration" name="storyboard_transition_duration" type="number" step="0.1" value="0.6">
                  </div>
                  <div class="field">
                    <label for="storyboard-video-trim-start">背景视频起始裁切</label>
                    <input id="storyboard-video-trim-start" name="storyboard_video_trim_start" type="number" step="0.1" value="0.4">
                  </div>
                  <div id="tencent-settings-group" class="conditional-group">
                  <div class="field">
                    <label for="tencent-appkey">腾讯云 AppKey</label>
                    <input id="tencent-appkey" name="tencent_appkey" placeholder="留空则读取环境变量">
                  </div>
                  <div class="field">
                    <label for="tencent-access-token">腾讯云 Access Token</label>
                    <input id="tencent-access-token" name="tencent_access_token" placeholder="留空则读取环境变量">
                  </div>
                  <div class="field full">
                    <label for="tencent-virtualman-key">腾讯云 VirtualmanKey</label>
                    <input id="tencent-virtualman-key" name="tencent_virtualman_key" placeholder="留空则读取环境变量">
                  </div>
                  </div>
                </div>
              </section>
            </div>
            <div class="submit-bar">
              <div class="submit-copy">留空的 Gemini、Pexels、腾讯云字段会优先读取本地 `.env` 或环境变量。页面与命令行共用同一条生成链路。</div>
              <button class="primary" type="submit" id="submit-job">开始生成</button>
            </div>
          </form>
        </div>
      </section>
      <aside class="panel side-panel" id="section-jobs">
        <div class="panel-head">
          <h2>任务状态</h2>
          <button class="secondary" type="button" id="refresh-btn">刷新</button>
        </div>
        <div class="panel-body">
          <div id="jobs" class="jobs"></div>
        </div>
      </aside>
    </div>
  </div>
  <script>
    const form = document.getElementById("job-form");
    const jobsEl = document.getElementById("jobs");
    const refreshBtn = document.getElementById("refresh-btn");
    const demoBtn = document.getElementById("fill-demo");
    const generateScriptBtn = document.getElementById("generate-script");
    const previewBtn = document.getElementById("preview-backgrounds");
    const refreshCandidatesBtn = document.getElementById("refresh-candidates");
    const previewVoiceBtn = document.getElementById("preview-voice");
    const uploadBackgroundBtn = document.getElementById("upload-background");
    const uploadBgmBtn = document.getElementById("upload-bgm");
    const submitJobBtn = document.getElementById("submit-job");
    const toastEl = document.getElementById("toast");
    const voiceFilterPills = Array.from(document.querySelectorAll("[data-voice-filter]"));
    const candidateGrid = document.getElementById("candidate-grid");
    const selectionChip = document.getElementById("selection-chip");
    const selectedStrip = document.getElementById("selected-strip");
    const videoModeEl = document.getElementById("video-mode");
    const creationModeEl = document.getElementById("creation-mode");
    const backgroundModeEl = document.getElementById("background-mode");
    const voiceEl = document.getElementById("voice");
    const voiceNoteEl = document.getElementById("voice-note");
    const geminiKeyStatusEl = document.getElementById("gemini-key-status");
    const pexelsKeyStatusEl = document.getElementById("pexels-key-status");
    const geminiReadyPillEl = document.getElementById("gemini-ready-pill");
    const pexelsReadyPillEl = document.getElementById("pexels-ready-pill");
    const whisperReadyPillEl = document.getElementById("whisper-ready-pill");
    const whisperModelSelectEl = document.getElementById("whisper-model-select");
    const manualBackgroundGroupEl = document.getElementById("manual-background-group");
    const backgroundPromptGroupEl = document.getElementById("background-prompt-group");
    const pexelsCandidateGroupEl = document.getElementById("pexels-candidate-group");
    const pexelsKeyGroupEl = document.getElementById("pexels-key-group");
    const webhookBackgroundConfigGroupEl = document.getElementById("webhook-background-config-group");
    const subtitleSettingsGroupEl = document.getElementById("subtitle-settings-group");
    const whisperSettingsGroupEl = document.getElementById("whisper-settings-group");
    const tencentSettingsGroupEl = document.getElementById("tencent-settings-group");
    const demoText = `凌晨三点的便利店，是都市最后的温柔乡。
霓虹灯在雨后的地面碎成星河，你捧着一杯热咖啡站在落地窗前，看这座永不沉睡的城。有人刚结束加班，有人正开始狂欢，而你的故事，藏在第47次深夜独处的沉默里。
我们总以为生活是一场马拉松，其实它更像深夜街头的自动贩卖机。你永远不知道下一罐会掉落什么口味，但冰凉的触感，总能让人清醒。
不必追赶黎明，你本身就是光。
献给所有在深夜里，依然选择相信明天的人。`;

    let selectedBackgroundAssets = [];
    let candidateRefreshPage = 1;
    let appConfigStatus = { gemini_api_key: false, pexels_api_key: false, whisper_model: false };

    voiceFilterPills.forEach((button) => {
      button.addEventListener("click", () => {
        voiceFilterPills.forEach((item) => item.classList.remove("active"));
        button.classList.add("active");
        applyVoiceFilter(button.dataset.voiceFilter || "all");
      });
    });

    voiceEl.addEventListener("change", updateVoiceNote);

    demoBtn.addEventListener("click", () => {
      selectedBackgroundAssets = [];
      document.getElementById("selected-background-assets").value = "";
      selectionChip.classList.remove("active");
      selectionChip.textContent = "";
      selectedStrip.classList.remove("active");
      selectedStrip.innerHTML = "";
      document.getElementById("idea").value = "我想做一条关于深夜便利店、都市孤独感和希望感的治愈系短视频。";
      document.getElementById("text").value = demoText;
      document.getElementById("video-mode").value = "storyboard";
      document.getElementById("creation-mode").value = "lazy";
      document.getElementById("background-mode").value = "pexels-video";
      document.getElementById("background-prompt").value =
        "midnight convenience store interior, neon reflections on rainy street, cinematic, cozy, realistic, 16:9";
      updateModeState();
    });

    generateScriptBtn.addEventListener("click", async () => {
      const payload = {
        idea: document.getElementById("idea").value.trim(),
        gemini_api_key: document.getElementById("gemini-api-key").value.trim(),
        gemini_model: (
          document.getElementById("gemini-model-custom").value.trim()
          || document.getElementById("gemini-model").value.trim()
        ),
        script_style: document.getElementById("script-style").value,
      };
      if (!payload.idea) {
        alert("请先写下你的想法。");
        return;
      }
      generateScriptBtn.disabled = true;
      generateScriptBtn.textContent = "正在生成文案...";
      try {
        const response = await fetch("/api/generate-script", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(payload)
        });
        const data = await response.json();
        if (!response.ok) throw new Error(data.error || "文案生成失败");
        if (data.title) {
          document.getElementById("title").value = data.title;
        }
        document.getElementById("text").value = data.text || "";
        if (data.background_prompt) {
          document.getElementById("background-prompt").value = data.background_prompt;
        }
        if (data.recommended_video_mode) {
          document.getElementById("video-mode").value = data.recommended_video_mode;
          updateModeState();
        }
      } catch (error) {
        alert(error.message);
      } finally {
        generateScriptBtn.disabled = false;
        generateScriptBtn.textContent = "AI 生成文案";
      }
    });

    previewBtn.addEventListener("click", () => {
      candidateRefreshPage = 1;
      loadPexelsCandidates(false);
    });
    refreshCandidatesBtn.addEventListener("click", () => {
      candidateRefreshPage += 1;
      loadPexelsCandidates(true);
    });
    previewVoiceBtn.addEventListener("click", previewVoiceSample);
    uploadBackgroundBtn.addEventListener("click", uploadBackgroundAsset);
    uploadBgmBtn.addEventListener("click", uploadBgmAsset);
    videoModeEl.addEventListener("change", updateModeState);
    creationModeEl.addEventListener("change", updateModeState);
    backgroundModeEl.addEventListener("change", updateModeState);
    document.getElementById("add-subtitles").addEventListener("change", updateModeState);
    document.getElementById("subtitle-provider").addEventListener("change", updateModeState);
    document.getElementById("whisper-model").addEventListener("input", updateModeState);
    whisperModelSelectEl.addEventListener("change", () => {
      const value = whisperModelSelectEl.value.trim();
      if (value) {
        document.getElementById("whisper-model").value = value;
      }
      updateModeState();
    });

    form.addEventListener("submit", async (event) => {
      event.preventDefault();
      const formData = new FormData(form);
      const payload = Object.fromEntries(formData.entries());
      payload.auto_split = document.getElementById("auto-split").checked;
      payload.add_subtitles = document.getElementById("add-subtitles").checked;
      payload.storyboard_dynamic_backgrounds = document.getElementById("storyboard-dynamic-backgrounds").checked;
      payload.storyboard_transitions = document.getElementById("storyboard-transitions").checked;
      payload.fast_mode = document.getElementById("fast-mode").checked;
      if (payload.creation_mode === "lazy") {
        payload.auto_split = true;
        payload.storyboard_dynamic_backgrounds = payload.background_mode === "pexels-video";
        payload.selected_background_assets = "";
      }
      submitJobBtn.disabled = true;
      submitJobBtn.textContent = "正在提交...";
      showToast("正在提交任务，浏览器不要关闭。任务开始后右侧会显示运行日志。");
      try {
        const response = await fetch("/api/jobs", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(payload)
        });
        const data = await response.json();
        if (!response.ok) throw new Error(data.error || "提交失败");
        showToast(`任务已开始生成：${data.title || data.id}。右侧任务状态会持续更新。`);
        await loadJobs();
      } catch (error) {
        alert(error.message);
      } finally {
        submitJobBtn.disabled = false;
        submitJobBtn.textContent = "开始生成";
      }
    });

    refreshBtn.addEventListener("click", loadJobs);

    async function loadPexelsCandidates(keepSelected) {
      const mode = backgroundModeEl.value;
      if (!["pexels", "pexels-video"].includes(mode)) {
        alert("候选预览目前支持 Pexels 背景图和 Pexels 背景视频。");
        return;
      }
      const prompt = document.getElementById("background-prompt").value.trim();
      if (!prompt) {
        alert("请先填写背景提示词。");
        return;
      }
      const payload = {
        background_mode: mode,
        background_prompt: prompt,
        text: document.getElementById("text").value.trim(),
        idea: document.getElementById("idea").value.trim(),
        pexels_api_key: document.getElementById("pexels-api-key").value.trim(),
        gemini_api_key: document.getElementById("gemini-api-key").value.trim(),
        exclude_asset_ids: selectedBackgroundAssets.map((item) => item.asset_id).filter(Boolean),
        refresh_page: candidateRefreshPage,
      };
      candidateGrid.innerHTML = keepSelected
        ? '<p class="tip">正在刷新未选候选，已选序列会保留...</p>'
        : '<p class="tip">正在检索候选背景，请稍候...</p>';
      previewBtn.disabled = true;
      refreshCandidatesBtn.disabled = true;
      try {
        const response = await fetch("/api/pexels-preview", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(payload)
        });
        const data = await response.json();
        if (!response.ok) throw new Error(data.error || "候选加载失败");
        renderCandidates(data.candidates || []);
      } catch (error) {
        candidateGrid.innerHTML = "";
        alert(error.message);
      } finally {
        previewBtn.disabled = false;
        refreshCandidatesBtn.disabled = false;
      }
    }

    function showToast(message) {
      toastEl.textContent = message;
      toastEl.classList.add("show");
      window.clearTimeout(showToast.timer);
      showToast.timer = window.setTimeout(() => {
        toastEl.classList.remove("show");
      }, 4200);
    }

    async function previewVoiceSample() {
      const payload = {
        voice: document.getElementById("voice").value,
        rate: document.getElementById("rate").value,
        volume: document.getElementById("volume").value,
        text: (document.getElementById("text").value || "你好，这是一段配音试听，我们正在为你生成一条短视频。").trim().slice(0, 60),
      };
      previewVoiceBtn.disabled = true;
      previewVoiceBtn.textContent = "正在试听...";
      try {
        const response = await fetch("/api/voice-preview", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(payload)
        });
        if (!response.ok) {
          const data = await response.json().catch(() => ({}));
          throw new Error(data.error || "试听失败");
        }
        const blob = await response.blob();
        const url = URL.createObjectURL(blob);
        const audio = new Audio(url);
        audio.onended = () => URL.revokeObjectURL(url);
        await audio.play();
      } catch (error) {
        alert(error.message);
      } finally {
        previewVoiceBtn.disabled = false;
        previewVoiceBtn.textContent = "试听 5 秒";
      }
    }

    async function uploadBackgroundAsset() {
      const result = await uploadLocalFile("background-upload", "background");
      if (!result) return;
      if (result.media_kind === "video") {
        document.getElementById("background-video").value = result.path;
        document.getElementById("background-image").value = "";
      } else if (result.media_kind === "image") {
        document.getElementById("background-image").value = result.path;
        document.getElementById("background-video").value = "";
      } else {
        alert("请上传图片或视频作为背景。");
        return;
      }
      backgroundModeEl.value = "manual";
      creationModeEl.value = "custom";
      selectedBackgroundAssets = [];
      syncSelectedBackgroundAssets();
      renderSelectedStrip();
      updateModeState();
      showToast("本地背景已上传并填入路径。");
    }

    async function uploadBgmAsset() {
      const result = await uploadLocalFile("bgm-upload", "bgm");
      if (!result) return;
      if (result.media_kind !== "audio") {
        alert("请上传音频文件作为 BGM。");
        return;
      }
      document.getElementById("bgm-audio").value = result.path;
      showToast("BGM 已上传并填入路径。");
    }

    async function uploadLocalFile(inputId, kind) {
      const input = document.getElementById(inputId);
      const file = input.files && input.files[0];
      if (!file) {
        alert("请先选择一个本地文件。");
        return null;
      }
      const formData = new FormData();
      formData.append("file", file);
      formData.append("kind", kind);
      showToast("正在上传本地文件...");
      const response = await fetch("/api/upload", {
        method: "POST",
        body: formData
      });
      const data = await response.json();
      if (!response.ok) {
        alert(data.error || "上传失败");
        return null;
      }
      return data;
    }

    function renderCandidates(candidates) {
      candidateGrid.innerHTML = "";
      if (!candidates.length) {
        candidateGrid.innerHTML = '<p class="tip">没有找到合适的候选背景，试试更具体的提示词。</p>';
        return;
      }
      candidates.forEach((candidate) => {
        const card = document.createElement("article");
        card.className = "candidate-card";
        const key = `${candidate.kind}:${candidate.asset_id || candidate.asset_url || candidate.label || ""}`;
        card.dataset.assetKey = key;
        if (selectedBackgroundAssets.some((item) => item._key === key)) {
          card.classList.add("selected");
        }
        const thumb = candidate.kind === "video"
          ? `<img class="candidate-media" src="${escapeAttr(candidate.preview_url || "")}" alt="${escapeAttr(candidate.label || '背景候选视频封面')}">`
          : `<img class="candidate-media" src="${escapeAttr(candidate.preview_url || candidate.asset_url)}" alt="${escapeAttr(candidate.label || '背景候选')}">`;
        card.innerHTML = `
          <div class="candidate-thumb">${thumb}</div>
          <div class="candidate-body">
            <strong>${escapeHtml(candidate.label || "候选背景")}</strong>
              <div class="candidate-meta">
                <div>素材 ID: ${escapeHtml(candidate.asset_id || "-")}</div>
                <div>检索词: ${escapeHtml(candidate.query || "-")}</div>
                <div>${candidate.kind === "video" ? "类型: 背景视频" : "类型: 背景图片"}</div>
                <div>${candidate.kind === "video" ? `素材时长: ${escapeHtml(formatSeconds(candidate.duration))}` : "素材时长: 静态图可自动延展"}</div>
              </div>
            <div class="candidate-actions">
              <button class="secondary" type="button">${selectedBackgroundAssets.some((item) => item._key === key) ? "已加入" : "加入候选"}</button>
            </div>
          </div>
        `;
        const button = card.querySelector("button");
        button.addEventListener("click", () => toggleCandidate(candidate, card, button));
        candidateGrid.appendChild(card);
      });
      renderSelectedStrip();
    }

    function toggleCandidate(candidate, card, button) {
      const key = `${candidate.kind}:${candidate.asset_id || candidate.asset_url || candidate.label || ""}`;
      const existingIndex = selectedBackgroundAssets.findIndex((item) => item._key === key);
      if (existingIndex >= 0) {
        selectedBackgroundAssets.splice(existingIndex, 1);
        card.classList.remove("selected");
        button.textContent = "加入候选";
      } else {
        selectedBackgroundAssets.push({ ...candidate, _key: key });
        card.classList.add("selected");
        button.textContent = "已加入";
      }
      syncSelectedBackgroundAssets();
      renderSelectedStrip();
    }

    function syncSelectedBackgroundAssets() {
      document.getElementById("selected-background-assets").value = JSON.stringify(
        selectedBackgroundAssets.map(({ _key, ...item }) => item)
      );
      if (selectedBackgroundAssets.length) {
        selectionChip.classList.add("active");
        selectionChip.textContent = buildSelectionHint();
      } else {
        selectionChip.classList.remove("active");
        selectionChip.textContent = "";
      }
    }

    function renderSelectedStrip() {
      selectedStrip.innerHTML = "";
      if (!selectedBackgroundAssets.length) {
        selectedStrip.classList.remove("active");
        return;
      }
      selectedStrip.classList.add("active");
      selectedBackgroundAssets.forEach((candidate, index) => {
        const card = document.createElement("article");
        card.className = "selected-card";
        const previewUrl = candidate.preview_url || candidate.asset_url || "";
        card.innerHTML = `
          <div class="candidate-thumb">
            <img src="${escapeAttr(previewUrl)}" alt="${escapeAttr(candidate.label || '已选背景')}">
          </div>
          <div class="selected-body">
            <div class="selected-order">片段 ${index + 1}</div>
            <div class="selected-title">${escapeHtml(candidate.label || candidate.asset_id || "未命名候选")}</div>
            <div class="candidate-meta">${escapeHtml(buildAssetDurationLabel(candidate))}</div>
            <div class="selected-actions">
              <button class="secondary" type="button" ${index === 0 ? "disabled" : ""}>左移</button>
              <button class="secondary" type="button" ${index === selectedBackgroundAssets.length - 1 ? "disabled" : ""}>右移</button>
              <button class="ghost" type="button">删除</button>
            </div>
          </div>
        `;
        const buttons = card.querySelectorAll("button");
        buttons[0].addEventListener("click", () => moveSelectedAsset(index, -1));
        buttons[1].addEventListener("click", () => moveSelectedAsset(index, 1));
        buttons[2].addEventListener("click", () => removeSelectedAsset(index));
        selectedStrip.appendChild(card);
      });
    }

    function moveSelectedAsset(index, direction) {
      const target = index + direction;
      if (target < 0 || target >= selectedBackgroundAssets.length) return;
      const [item] = selectedBackgroundAssets.splice(index, 1);
      selectedBackgroundAssets.splice(target, 0, item);
      syncSelectedBackgroundAssets();
      renderSelectedStrip();
    }

    function buildSelectionHint() {
      const base = `已选择 ${selectedBackgroundAssets.length} 条背景素材。生成时会按当前顺序播放，素材播完会切下一条，列表用完后才循环。`;
      const totalBackgroundDuration = selectedBackgroundAssets.reduce((sum, asset) => {
        return sum + (asset.kind === "video" ? Number(asset.duration || 0) : 9999);
      }, 0);
      const totalNarrationDuration = estimateTotalNarrationDuration();
      if (!totalNarrationDuration || totalBackgroundDuration >= 9999) {
        return `${base} 当前包含静态图或暂无法估算总旁白时长。`;
      }
      if (!totalBackgroundDuration) {
        return `${base} 当前视频素材缺少时长信息，可能需要生成后确认。`;
      }
      const summary = `已选素材总时长约 ${formatSeconds(totalBackgroundDuration)}，预计旁白总时长约 ${formatSeconds(totalNarrationDuration)}。`;
      if (totalBackgroundDuration < totalNarrationDuration) {
        return `${base} ${summary} 背景序列可能会从头再循环。`;
      }
      return `${base} ${summary} 背景序列长度基本够用。`;
    }

    function buildAssetDurationLabel(asset) {
      if (asset.kind !== "video") return "静态图：可自动延展";
      const assetDuration = Number(asset.duration || 0);
      return `素材时长：${formatSeconds(assetDuration)}`;
    }

    function estimateTotalNarrationDuration() {
      return estimateSegmentDurations().reduce((sum, value) => sum + value, 0);
    }

    function estimateSegmentDurations() {
      const text = document.getElementById("text").value.trim();
      if (!text) return [];
      const maxChars = Math.max(20, Number(document.getElementById("split-max-chars").value || 120));
      const chunks = [];
      let current = "";
      text.split(/(?<=[。！？!?\\n])/).forEach((part) => {
        const sentence = part.trim();
        if (!sentence) return;
        if ((current + sentence).length > maxChars && current) {
          chunks.push(current);
          current = sentence;
        } else {
          current += sentence;
        }
      });
      if (current) chunks.push(current);
      return chunks.map((chunk) => Math.max(4, chunk.length * 0.22));
    }

    function formatSeconds(value) {
      const seconds = Number(value || 0);
      if (!seconds) return "-";
      return `${Math.round(seconds)}秒`;
    }

    function removeSelectedAsset(index) {
      const [removed] = selectedBackgroundAssets.splice(index, 1);
      if (removed) {
        const key = removed._key;
        document.querySelectorAll(".candidate-card.selected").forEach((node) => {
          const assetKey = node.dataset.assetKey || "";
          if (assetKey === key) {
            node.classList.remove("selected");
            const btn = node.querySelector("button");
            if (btn) btn.textContent = "加入候选";
          }
        });
      }
      syncSelectedBackgroundAssets();
      renderSelectedStrip();
    }

    function updateModeState() {
      const isStoryboard = videoModeEl.value === "storyboard";
      const isLazy = creationModeEl.value === "lazy";
      const isWhisper = document.getElementById("subtitle-provider").value === "whisper";
      const backgroundMode = backgroundModeEl.value;
      const whisperModelConfigured = appConfigStatus.whisper_model || document.getElementById("whisper-model").value.trim();
      document.getElementById("storyboard-dynamic-backgrounds").disabled = !isStoryboard;
      document.getElementById("storyboard-transitions").disabled = !isStoryboard;
      document.getElementById("storyboard-transition-duration").disabled = !isStoryboard;
      document.getElementById("storyboard-video-trim-start").disabled = !isStoryboard;
      document.getElementById("whisper-model").disabled = !isWhisper;
      document.getElementById("whisper-language").disabled = !isWhisper;
      manualBackgroundGroupEl.classList.toggle("is-hidden", backgroundMode !== "manual");
      backgroundPromptGroupEl.classList.toggle("is-hidden", !["pexels", "pexels-video", "webhook"].includes(backgroundMode));
      pexelsCandidateGroupEl.classList.toggle("is-hidden", !["pexels", "pexels-video"].includes(backgroundMode) || isLazy);
      pexelsKeyGroupEl.classList.toggle("is-hidden", !["pexels", "pexels-video"].includes(backgroundMode));
      webhookBackgroundConfigGroupEl.classList.toggle("is-hidden", backgroundMode !== "webhook");
      subtitleSettingsGroupEl.classList.toggle("is-hidden", !document.getElementById("add-subtitles").checked);
      whisperSettingsGroupEl.classList.toggle("is-hidden", !document.getElementById("add-subtitles").checked || !isWhisper);
      tencentSettingsGroupEl.classList.toggle("is-hidden", videoModeEl.value !== "tencent");
      if (whisperModelConfigured) {
        whisperReadyPillEl.textContent = appConfigStatus.whisper_model
          ? "Whisper 模型已就绪"
          : "Whisper 路径已填写，提交时会校验模型文件";
        whisperReadyPillEl.className = `status-pill ${appConfigStatus.whisper_model ? "ok" : "warn"}`;
      } else if (isWhisper) {
        whisperReadyPillEl.textContent = "Whisper 模型未配置，精准模式需先填写模型路径";
        whisperReadyPillEl.className = "status-pill warn";
      } else if (!appConfigStatus.whisper_model) {
        whisperReadyPillEl.textContent = "Whisper 模型未配置";
        whisperReadyPillEl.className = "status-pill warn";
      }
      const supportsPreview = ["pexels", "pexels-video"].includes(backgroundModeEl.value);
      previewBtn.textContent = supportsPreview ? (isLazy ? "懒人模式通常无需预览" : "预览候选背景") : "切换到 Pexels 后可预览";
      refreshCandidatesBtn.classList.toggle("is-hidden", !supportsPreview || isLazy);
    }

    function applyVoiceFilter(filter) {
      const options = Array.from(voiceEl.options);
      let firstVisibleValue = "";
      options.forEach((option) => {
        const group = option.dataset.group || "all";
        const visible = filter === "all" || group === filter;
        option.hidden = !visible;
        if (visible && !firstVisibleValue) firstVisibleValue = option.value;
      });
      if (voiceEl.selectedOptions.length === 0 || voiceEl.selectedOptions[0].hidden) {
        voiceEl.value = firstVisibleValue || voiceEl.value;
      }
      updateVoiceNote();
    }

    function updateVoiceNote() {
      const selected = voiceEl.selectedOptions[0];
      voiceNoteEl.textContent = selected?.dataset.note || "选择一个音色后，这里会显示适合场景。";
    }

    async function loadJobs() {
      const response = await fetch("/api/jobs");
      const jobs = await response.json();
      if (!Array.isArray(jobs)) return;
      jobsEl.innerHTML = "";
      if (jobs.length === 0) {
        jobsEl.innerHTML = '<p class="tip">还没有任务，先在左侧提交一个吧。</p>';
        return;
      }
      for (const job of jobs) {
        const card = document.createElement("article");
        card.className = "job";
        const statusClass = job.status === "success" ? "success" : job.status === "failed" ? "failed" : (job.status || "queued");
        card.innerHTML = `
          <div class="status ${statusClass}">${job.status}</div>
          <h3>${escapeHtml(job.title || job.id)}</h3>
          <div class="meta">
            <div>任务 ID: ${escapeHtml(job.id)}</div>
            <div>视频模式: ${escapeHtml(job.video_mode || "-")}</div>
            <div>创作模式: ${escapeHtml(job.creation_mode || "-")}</div>
            <div>背景方式: ${escapeHtml(job.background_mode || "-")}</div>
            <div>提交时间: ${escapeHtml(formatJobTime(job.created_at))}</div>
            <div>开始时间: ${escapeHtml(formatJobTime(job.started_at))}</div>
            <div>完成时间: ${escapeHtml(formatJobTime(job.finished_at))}</div>
            <div>耗时: ${escapeHtml(formatJobDuration(job))}</div>
            <div>输出目录: ${escapeHtml(job.output_dir || "-")}</div>
            <div>最终视频: ${escapeHtml(job.final_video_path || "-")}</div>
          </div>
          ${job.final_video_path ? `
            <div class="actions-row">
              <a class="pill" href="/api/file?job_id=${encodeURIComponent(job.id)}&kind=video" target="_blank">预览视频</a>
              <a class="pill" href="/api/file?job_id=${encodeURIComponent(job.id)}&kind=video&download=1">下载视频</a>
              <a class="pill" href="/api/file?job_id=${encodeURIComponent(job.id)}&kind=log" target="_blank">查看日志</a>
            </div>
            <video controls preload="metadata" src="/api/file?job_id=${encodeURIComponent(job.id)}&kind=video"></video>
          ` : ""}
          <pre>${escapeHtml(job.log || "")}</pre>
        `;
        jobsEl.appendChild(card);
      }
    }

    function escapeHtml(value) {
      return String(value)
        .replaceAll("&", "&amp;")
        .replaceAll("<", "&lt;")
        .replaceAll(">", "&gt;");
    }

    function formatJobTime(value) {
      const timestamp = Number(value || 0);
      if (!timestamp) return "-";
      return new Date(timestamp * 1000).toLocaleString();
    }

    function formatJobDuration(job) {
      const start = Number(job.started_at || 0);
      const end = Number(job.finished_at || 0);
      if (!start) return "-";
      const seconds = Math.max(0, Math.round((end || Date.now() / 1000) - start));
      const minutes = Math.floor(seconds / 60);
      const rest = seconds % 60;
      return minutes ? `${minutes}分${rest}秒` : `${rest}秒`;
    }

    async function loadConfigStatus() {
      try {
        const response = await fetch("/api/config-status");
        const status = await response.json();
        appConfigStatus = status;
        geminiKeyStatusEl.textContent = status.gemini_api_key
          ? "已读取本地 Gemini 配置，页面可留空。"
          : "未读取到 Gemini 配置，请在 .env 中填写 GEMINI_API_KEY，或在页面手动输入。";
        pexelsKeyStatusEl.textContent = status.pexels_api_key
          ? "已读取本地 Pexels 配置，页面可留空。"
          : "未读取到 Pexels 配置，请在 .env 中填写 PEXELS_API_KEY，或在页面手动输入。";
        geminiReadyPillEl.textContent = status.gemini_api_key ? "Gemini 已就绪" : "Gemini 未配置";
        geminiReadyPillEl.className = `status-pill ${status.gemini_api_key ? "ok" : "warn"}`;
        pexelsReadyPillEl.textContent = status.pexels_api_key ? "Pexels 已就绪" : "Pexels 未配置";
        pexelsReadyPillEl.className = `status-pill ${status.pexels_api_key ? "ok" : "warn"}`;
        whisperReadyPillEl.textContent = status.whisper_model ? "Whisper 模型已就绪" : "Whisper 模型未配置";
        whisperReadyPillEl.className = `status-pill ${status.whisper_model ? "ok" : "warn"}`;
        populateWhisperModels(status.whisper_models || [], status.whisper_model_path || "");
        updateModeState();
      } catch (error) {
        appConfigStatus = { gemini_api_key: false, pexels_api_key: false, whisper_model: false };
        geminiKeyStatusEl.textContent = "配置状态检测失败，可先手动输入。";
        pexelsKeyStatusEl.textContent = "配置状态检测失败，可先手动输入。";
        geminiReadyPillEl.textContent = "Gemini 状态未知";
        pexelsReadyPillEl.textContent = "Pexels 状态未知";
        whisperReadyPillEl.textContent = "Whisper 状态未知";
        geminiReadyPillEl.className = "status-pill warn";
        pexelsReadyPillEl.className = "status-pill warn";
        whisperReadyPillEl.className = "status-pill warn";
      }
    }

    function populateWhisperModels(models, configuredPath) {
      const currentPath = document.getElementById("whisper-model").value.trim();
      whisperModelSelectEl.innerHTML = '<option value="">手动输入或等待自动检测</option>';
      (models || []).forEach((item) => {
        const option = document.createElement("option");
        option.value = item.path || "";
        option.textContent = item.label || item.path || "未命名模型";
        whisperModelSelectEl.appendChild(option);
      });
      const preferred = currentPath || configuredPath || "";
      if (preferred) {
        const matched = Array.from(whisperModelSelectEl.options).some((option) => option.value === preferred);
        if (matched) {
          whisperModelSelectEl.value = preferred;
        }
        if (!currentPath) {
          document.getElementById("whisper-model").value = preferred;
        }
      }
    }

    function escapeAttr(value) {
      return escapeHtml(value).replaceAll('"', "&quot;");
    }

    applyVoiceFilter("all");
    updateModeState();
    loadConfigStatus();
    loadJobs();
    setInterval(loadJobs, 5000);
  </script>
</body>
</html>
"""


@dataclass
class WebJob:
    id: str
    title: str
    status: str
    payload: dict[str, Any]
    output_dir: str
    log: str = ""
    final_video_path: str = ""
    created_at: float = field(default_factory=time.time)
    started_at: float = 0.0
    finished_at: float = 0.0
    process: subprocess.Popen[str] | None = field(default=None, repr=False)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "title": self.title,
            "status": self.status,
            "video_mode": self.payload.get("video_mode") or "-",
            "creation_mode": self.payload.get("creation_mode") or "-",
            "background_mode": self.payload.get("background_mode") or "-",
            "output_dir": self.output_dir,
            "final_video_path": self.final_video_path,
            "log": self.log[-8000:],
            "created_at": self.created_at,
            "started_at": self.started_at,
            "finished_at": self.finished_at,
        }


JOB_STORE: dict[str, WebJob] = {}
JOB_LOCK = threading.Lock()


def build_command(payload: dict[str, Any], output_dir: Path) -> list[str]:
    command = [sys.executable, str(BASE_DIR / "video_pipeline.py")]
    title = (payload.get("title") or "web_job").strip()
    text = (payload.get("text") or "").strip()
    if not text:
        raise ValueError("文案不能为空。")

    command += ["--title", title, "--text", text, "--output-dir", str(output_dir)]
    command += ["--video-mode", str(payload.get("video_mode") or "storyboard")]
    append_if_present(command, "--voice", payload.get("voice"))
    append_if_present(command, "--rate", payload.get("rate"))
    append_if_present(command, "--volume", payload.get("volume"))

    if payload.get("auto_split"):
        command.append("--auto-split")
        command += ["--split-max-chars", str(payload.get("split_max_chars") or 120)]
    if payload.get("storyboard_dynamic_backgrounds"):
        command.append("--storyboard-dynamic-backgrounds")
    if payload.get("storyboard_transitions"):
        command.append("--storyboard-transitions")
        command += ["--storyboard-transition-duration", str(payload.get("storyboard_transition_duration") or 0.6)]
    if payload.get("fast_mode"):
        command.append("--fast-mode")
    append_if_present(command, "--storyboard-video-trim-start", payload.get("storyboard_video_trim_start"))
    append_if_present(command, "--storyboard-backgrounds-manifest", payload.get("storyboard_backgrounds_manifest"))
    if payload.get("add_subtitles"):
        command.append("--add-subtitles")
        append_if_present(command, "--subtitle-provider", payload.get("subtitle_provider"))
        command += ["--subtitle-max-chars", str(payload.get("subtitle_max_chars") or 22)]
        command += ["--subtitle-font-size", str(payload.get("subtitle_font_size") or 18)]
        command += ["--subtitle-bar-height", str(payload.get("subtitle_bar_height") or 170)]
        command += ["--subtitle-bar-opacity", str(payload.get("subtitle_bar_opacity") or 0.34)]
        append_if_present(command, "--subtitle-offset", payload.get("subtitle_offset"))
        append_if_present(command, "--whisper-model", payload.get("whisper_model"))
        append_if_present(command, "--whisper-language", payload.get("whisper_language"))
    append_if_present(command, "--bgm-audio", payload.get("bgm_audio"))
    append_if_present(command, "--bgm-volume", payload.get("bgm_volume"))

    append_if_present(command, "--tencent-appkey", payload.get("tencent_appkey"))
    append_if_present(command, "--tencent-access-token", payload.get("tencent_access_token"))
    append_if_present(command, "--tencent-virtualman-key", payload.get("tencent_virtualman_key"))

    background_mode = payload.get("background_mode") or "manual"
    video_mode = str(payload.get("video_mode") or "storyboard")
    has_manual_background = bool(str(payload.get("background_image") or "").strip() or str(payload.get("background_video") or "").strip())
    has_selected_background = bool(str(payload.get("selected_background_asset_url") or "").strip())
    has_background_prompt = bool(str(payload.get("background_prompt") or "").strip())
    if (
        video_mode == "storyboard"
        and background_mode in {"manual", "none"}
        and not has_manual_background
        and not has_selected_background
    ):
        background_mode = "pexels-video"
    command += ["--background-mode", background_mode]
    if background_mode == "manual":
        append_if_present(command, "--background-image", payload.get("background_image"))
        append_if_present(command, "--background-video", payload.get("background_video"))
    elif background_mode == "pexels":
        append_if_present(command, "--background-prompt", payload.get("background_prompt"))
        append_if_present(command, "--pexels-api-key", resolve_secret(payload.get("pexels_api_key"), "PEXELS_API_KEY"))
    elif background_mode == "pexels-video":
        append_if_present(command, "--background-prompt", payload.get("background_prompt"))
        append_if_present(command, "--pexels-api-key", resolve_secret(payload.get("pexels_api_key"), "PEXELS_API_KEY"))
    elif background_mode == "webhook":
        append_if_present(command, "--background-prompt", payload.get("background_prompt"))
        append_if_present(command, "--background-config", payload.get("background_config"))

    append_if_present(command, "--background-similarity", payload.get("background_similarity"))
    append_if_present(command, "--background-blend", payload.get("background_blend"))
    append_if_present(command, "--background-despill", payload.get("background_despill"))
    append_if_present(command, "--background-shadow", payload.get("background_shadow"))
    append_if_present(command, "--background-feather", payload.get("background_feather"))
    append_if_present(command, "--subject-scale", payload.get("subject_scale"))
    append_if_present(command, "--subject-offset-y", payload.get("subject_offset_y"))
    append_if_present(command, "--subject-saturation", payload.get("subject_saturation"))
    append_if_present(command, "--subject-gamma", payload.get("subject_gamma"))
    return command


def validate_job_payload(payload: dict[str, Any]) -> None:
    video_mode = str(payload.get("video_mode") or "storyboard")
    if video_mode != "tencent":
        return
    missing: list[str] = []
    if not resolve_secret(payload.get("tencent_appkey"), "TENCENT_DH_APPKEY"):
        missing.append("腾讯云 AppKey")
    if not resolve_secret(payload.get("tencent_access_token"), "TENCENT_DH_ACCESS_TOKEN"):
        missing.append("腾讯云 Access Token")
    if not resolve_secret(payload.get("tencent_virtualman_key"), "TENCENT_DH_VIRTUALMAN_KEY"):
        missing.append("腾讯云 VirtualmanKey")
    if missing:
        raise ValueError(
            "数字人口播模式缺少参数："
            + "、".join(missing)
            + "。请在页面填写，或在 .env 中配置 TENCENT_DH_APPKEY / TENCENT_DH_ACCESS_TOKEN / TENCENT_DH_VIRTUALMAN_KEY。"
        )


def append_if_present(command: list[str], flag: str, value: Any) -> None:
    if value is None:
        return
    text = str(value).strip()
    if text == "":
        return
    command += [flag, text]


def is_placeholder_secret(value: str) -> bool:
    return pipeline_script.is_placeholder_env_value(value)


def resolve_secret(value: Any, env_name: str) -> str:
    inline_value = str(value or "").strip()
    if inline_value and not is_placeholder_secret(inline_value):
        return inline_value
    env_value = str(os.getenv(env_name) or "").strip()
    if env_value and not is_placeholder_secret(env_value):
        return env_value
    return ""


def discover_whisper_models() -> list[dict[str, str]]:
    discovered: list[dict[str, str]] = []
    seen_paths: set[str] = set()
    search_dirs = [BASE_DIR / "models"]
    env_model = str(os.getenv("WHISPER_MODEL_PATH") or "").strip()
    if env_model and not is_placeholder_secret(env_model):
        env_path = Path(env_model).expanduser()
        if env_path.exists():
            path_str = str(env_path)
            seen_paths.add(path_str)
            discovered.append({"label": env_path.name, "path": path_str})
    for search_dir in search_dirs:
        if not search_dir.exists():
            continue
        for pattern in ("ggml-*.bin", "*.gguf"):
            for model_path in sorted(search_dir.glob(pattern)):
                path_str = str(model_path)
                if path_str in seen_paths:
                    continue
                seen_paths.add(path_str)
                discovered.append({"label": model_path.name, "path": path_str})
    return discovered


def config_status() -> dict[str, Any]:
    whisper_model_path = str(os.getenv("WHISPER_MODEL_PATH") or "").strip()
    whisper_model_ready = bool(
        whisper_model_path
        and not is_placeholder_secret(whisper_model_path)
        and Path(whisper_model_path).exists()
    )
    return {
        "gemini_api_key": bool(resolve_secret("", "GEMINI_API_KEY")),
        "pexels_api_key": bool(resolve_secret("", "PEXELS_API_KEY")),
        "whisper_model": whisper_model_ready,
        "whisper_model_path": whisper_model_path,
        "whisper_models": discover_whisper_models(),
        "env_path": str(BASE_DIR / ".env"),
    }


def extract_json_block(text: str) -> dict[str, Any]:
    cleaned = text.strip()
    if cleaned.startswith("```"):
        lines = [line for line in cleaned.splitlines() if not line.strip().startswith("```")]
        cleaned = "\n".join(lines).strip()
    start = cleaned.find("{")
    end = cleaned.rfind("}")
    if start == -1 or end == -1 or end <= start:
        raise ValueError("AI 返回内容中没有找到 JSON。")
    return json.loads(cleaned[start : end + 1])


def clean_generated_text(value: str) -> str:
    text = value.strip()
    if text.startswith("[") and text.endswith("]"):
        try:
            parsed = ast.literal_eval(text)
        except (SyntaxError, ValueError):
            parsed = None
        if isinstance(parsed, (list, tuple)):
            text = "\n".join(str(item).strip() for item in parsed if str(item).strip())
    text = text.replace("', '", "\n").replace('", "', "\n")
    for prefix, suffix in (("['", "']"), ('["', '"]')):
        if text.startswith(prefix) and text.endswith(suffix):
            text = text[len(prefix) : -len(suffix)]
    return text.strip()


def normalize_ai_text(value: Any, separator: str = "\n") -> str:
    if value is None:
        return ""
    if isinstance(value, (list, tuple)):
        return separator.join(
            normalize_ai_text(item, separator=separator)
            for item in value
            if normalize_ai_text(item, separator=separator)
        ).strip()
    if isinstance(value, dict):
        return separator.join(
            normalize_ai_text(item, separator=separator)
            for item in value.values()
            if normalize_ai_text(item, separator=separator)
        ).strip()
    return clean_generated_text(str(value))


def generate_script_draft(payload: dict[str, Any]) -> dict[str, Any]:
    idea = str(payload.get("idea") or "").strip()
    if not idea:
        raise ValueError("请先输入你的想法。")
    style = str(payload.get("script_style") or "healing").strip()

    api_key = resolve_secret(payload.get("gemini_api_key"), "GEMINI_API_KEY")
    if not api_key:
        raise ValueError("缺少 Gemini API Key。请填写页面中的 Gemini API Key，或在项目 .env / 环境变量 GEMINI_API_KEY 中配置。")

    model = str(payload.get("gemini_model") or os.getenv("GEMINI_TEXT_MODEL") or DEFAULT_GEMINI_TEXT_MODELS[0]).strip()
    style_instructions = {
        "healing": "整体气质温柔、治愈、有画面感，适合情绪向短视频。",
        "tech": "整体气质冷静、未来感、节奏利落，适合 AI、科技、效率主题短视频。",
        "product": "整体气质清晰、直接、可信，适合产品介绍、功能讲解、品牌口播。",
    }
    selected_style_instruction = style_instructions.get(style, style_instructions["healing"])
    requests = pipeline_script.import_requests()
    request_payload = {
        "system_instruction": {
            "parts": [
                {
                    "text": (
                    "你是中文短视频文案策划。根据用户给出的想法，输出严格 JSON。"
                    "不要输出任何 JSON 之外的解释。"
                    "JSON 必须包含四个字段："
                    "title: 简短的视频标题或任务名，8 到 16 个中文字符，不要标点堆砌；"
                    "script: 可直接用于口播的中文文案；"
                    "background_prompt: 适合 Pexels 检索的英文背景提示词；"
                    "recommended_video_mode: 只能是 storyboard 或 tencent。"
                        "要求：script 自然、连贯、有画面感；不要标题，不要编号；"
                        "输出 6 到 10 句，适合 30 到 60 秒短视频；"
                        "句子长度适中，便于后续自动分段和字幕生成。"
                        "background_prompt 要具体、克制、适合真实素材检索，优先场景名词，少用抽象形容词。"
                        "如果内容更依赖氛围、画面、旁白、场景切换，recommended_video_mode 设为 storyboard；"
                        "如果内容更适合真人/主播/口播讲解，recommended_video_mode 设为 tencent。"
                        f"{selected_style_instruction}"
                    )
                }
            ]
        },
        "contents": [
            {
                "role": "user",
                "parts": [
                    {
                        "text": f"请根据这个想法生成结果：{idea}"
                    }
                ],
            }
        ],
        "generationConfig": {
            "temperature": 0.8,
            "responseMimeType": "application/json",
        },
    }
    response, used_model = post_gemini_with_fallbacks(requests, model, api_key, request_payload)
    data = response.json()
    raw_text = str(
        ((((data.get("candidates") or [{}])[0]).get("content") or {}).get("parts") or [{}])[0].get("text") or ""
    ).strip()
    if not raw_text:
        raise RuntimeError("AI 接口已返回结果，但没有提取到文案内容。")
    result = extract_json_block(raw_text)
    title = normalize_ai_text(result.get("title"), separator=" ").strip()
    script = normalize_ai_text(result.get("script"), separator="\n").strip()
    background_prompt = normalize_ai_text(result.get("background_prompt"), separator=", ").strip()
    recommended_video_mode = normalize_ai_text(result.get("recommended_video_mode"), separator=" ").strip().lower()
    if not script:
        raise RuntimeError("AI 返回成功，但缺少 script 字段。")
    if recommended_video_mode not in {"storyboard", "tencent"}:
        recommended_video_mode = "storyboard"
    return {
        "title": title,
        "text": script,
        "background_prompt": background_prompt,
        "recommended_video_mode": recommended_video_mode,
        "model": used_model,
        "style": style,
    }


def unique_gemini_models(preferred_model: str) -> list[str]:
    env_fallbacks = [
        item.strip()
        for item in str(os.getenv("GEMINI_TEXT_FALLBACK_MODELS") or "").split(",")
        if item.strip()
    ]
    models: list[str] = []
    for item in [preferred_model, *env_fallbacks, *DEFAULT_GEMINI_TEXT_MODELS]:
        if item and item not in models:
            models.append(item)
    return models


def post_gemini_with_fallbacks(
    requests_module: Any,
    preferred_model: str,
    api_key: str,
    payload: dict[str, Any],
) -> tuple[Any, str]:
    models = unique_gemini_models(preferred_model)
    transient_errors: list[str] = []
    for model in models:
        try:
            response = post_gemini_with_retries(requests_module, model, api_key, payload)
            if model != preferred_model:
                print(f"[提示] Gemini 当前模型不可用，已自动切换到 {model}", file=sys.stderr)
            return response, model
        except Exception as exc:
            status_code = get_http_status_code(exc)
            if status_code in {429, 500, 502, 503, 504}:
                transient_errors.append(format_gemini_error(model, exc))
                continue
            raise

    details = "；".join(transient_errors[-3:]) or "没有可用的备用模型。"
    raise RuntimeError(
        "Gemini 文案接口暂时不可用，已自动尝试备用模型但仍失败。"
        "这通常是 Google 服务繁忙、配额限流或代理网络波动导致的。"
        f"已尝试模型: {', '.join(models)}。最后错误: {details}"
    )


def post_gemini_with_retries(
    requests_module: Any,
    model: str,
    api_key: str,
    payload: dict[str, Any],
    max_attempts: int = 3,
) -> Any:
    retry_statuses = {429, 500, 502, 503, 504}
    delay_seconds = [2, 5, 10]
    last_response: Any = None
    for attempt in range(max_attempts):
        response = requests_module.post(
            f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent",
            headers={
                "x-goog-api-key": api_key,
                "Content-Type": "application/json",
            },
            json=payload,
            timeout=120,
        )
        if response.status_code not in retry_statuses:
            response.raise_for_status()
            return response
        last_response = response
        if attempt < max_attempts - 1:
            time.sleep(delay_seconds[min(attempt, len(delay_seconds) - 1)])
    assert last_response is not None
    last_response.raise_for_status()
    return last_response


def get_http_status_code(exc: Exception) -> int | None:
    response = getattr(exc, "response", None)
    status_code = getattr(response, "status_code", None)
    return int(status_code) if status_code else None


def format_gemini_error(model: str, exc: Exception) -> str:
    response = getattr(exc, "response", None)
    status_code = getattr(response, "status_code", "未知状态")
    text = str(getattr(response, "text", "") or str(exc)).strip()
    if len(text) > 220:
        text = text[:220] + "..."
    return f"{model}: HTTP {status_code}, {text}"


def generate_voice_preview(payload: dict[str, Any]) -> bytes:
    voice = str(payload.get("voice") or "zh-CN-XiaoxiaoNeural").strip()
    rate = str(payload.get("rate") or "+0%").strip()
    volume = str(payload.get("volume") or "+0%").strip()
    text = str(payload.get("text") or "你好，这是一段配音试听。").strip()
    preview_text = text[:60] or "你好，这是一段配音试听。"
    preview_dir = OUTPUT_DIR / "_previews"
    preview_dir.mkdir(parents=True, exist_ok=True)
    output_path = preview_dir / f"voice_preview_{uuid.uuid4().hex[:8]}.mp3"
    asyncio.run(
        pipeline_script.EdgeTTSProvider().synthesize(
            text=preview_text,
            output_path=output_path,
            voice=voice,
            rate=rate,
            volume=volume,
        )
    )
    try:
        return output_path.read_bytes()
    finally:
        if output_path.exists():
            output_path.unlink()


def search_pexels_candidates(payload: dict[str, Any]) -> list[dict[str, Any]]:
    background_mode = str(payload.get("background_mode") or "pexels-video")
    prompt = resolve_pexels_prompt(payload)
    api_key = resolve_secret(payload.get("pexels_api_key"), "PEXELS_API_KEY")
    if background_mode not in {"pexels", "pexels-video"}:
        raise ValueError("只有 Pexels 背景图和 Pexels 背景视频支持候选预览。")
    if not prompt:
        raise ValueError("请先填写背景提示词。")
    if not api_key:
        raise ValueError("缺少 Pexels API Key。请填写页面中的 Pexels API Key，或在项目 .env / 环境变量 PEXELS_API_KEY 中配置。")

    requests = pipeline_script.import_requests()
    per_page = 6
    candidates: list[dict[str, Any]] = []
    excluded_ids = {
        str(item).strip()
        for item in (payload.get("exclude_asset_ids") or [])
        if str(item).strip()
    }
    seen_ids: set[str] = set(excluded_ids)
    refresh_page = max(1, int(payload.get("refresh_page") or 1))
    page_window = range(refresh_page, refresh_page + 3)

    scene_queries = build_grouped_pexels_queries(prompt)
    if background_mode == "pexels":
        provider = pipeline_script.PexelsBackgroundProvider(api_key)
        for query in scene_queries or sanitize_pexels_queries(provider.build_queries(prompt)):
            for page in page_window:
                response = safe_pexels_get(
                    requests,
                    provider.search_url,
                    api_key,
                    {
                        "query": query,
                        "orientation": "landscape",
                        "size": "large",
                        "locale": "en-US",
                        "per_page": per_page,
                        "page": page,
                    },
                )
                if response is None:
                    continue
                response.raise_for_status()
                for photo in response.json().get("photos") or []:
                    asset_id = str(photo.get("id") or "")
                    if not asset_id or asset_id in seen_ids:
                        continue
                    seen_ids.add(asset_id)
                    source = photo.get("src") or {}
                    asset_url = source.get("landscape") or source.get("large2x") or source.get("large") or source.get("original")
                    preview_url = source.get("medium") or asset_url
                    if not asset_url:
                        continue
                    candidates.append(
                        {
                            "asset_id": asset_id,
                            "kind": "image",
                            "label": photo.get("alt") or "Pexels 背景图",
                            "query": query,
                            "preview_url": preview_url,
                            "asset_url": asset_url,
                            "_creator_key": str((photo.get("photographer_id") or photo.get("photographer") or "")),
                            "_series_key": build_pexels_series_key(photo.get("url") or photo.get("alt") or asset_url),
                        }
                    )
    else:
        provider = pipeline_script.PexelsVideoBackgroundProvider(api_key)
        for query in scene_queries or sanitize_pexels_queries(provider.build_queries(prompt)):
            for page in page_window:
                response = safe_pexels_get(
                    requests,
                    provider.search_url,
                    api_key,
                    {
                        "query": query,
                        "orientation": "landscape",
                        "size": "medium",
                        "per_page": per_page,
                        "page": page,
                    },
                )
                if response is None:
                    continue
                response.raise_for_status()
                for video in response.json().get("videos") or []:
                    asset_id = str(video.get("id") or "")
                    if not asset_id or asset_id in seen_ids:
                        continue
                    file_info = provider.select_best_video_file(video.get("video_files") or [])
                    if not file_info:
                        continue
                    seen_ids.add(asset_id)
                    preview_url = ""
                    pictures = video.get("video_pictures") or []
                    if pictures:
                        preview_url = str((pictures[0] or {}).get("picture") or "")
                    user = video.get("user") or {}
                    candidates.append(
                        {
                            "asset_id": asset_id,
                            "kind": "video",
                            "label": video.get("url") or "Pexels 背景视频",
                            "query": query,
                            "preview_url": preview_url,
                            "asset_url": str(file_info.get("link") or ""),
                            "duration": int(video.get("duration") or 0),
                            "_creator_key": str(user.get("id") or user.get("name") or ""),
                            "_series_key": build_pexels_series_key(video.get("url") or file_info.get("link") or ""),
                        }
                    )
    return pick_diverse_pexels_candidates(candidates, per_page)

def pick_diverse_pexels_candidates(candidates: list[dict[str, Any]], limit: int) -> list[dict[str, Any]]:
    selected: list[dict[str, Any]] = []
    selected_ids: set[str] = set()
    used_queries: set[str] = set()
    used_creators: set[str] = set()
    used_series: set[str] = set()

    def try_add(
        item: dict[str, Any],
        require_new_query: bool,
        require_new_creator: bool,
        require_new_series: bool,
    ) -> None:
        if len(selected) >= limit:
            return
        asset_id = str(item.get("asset_id") or "")
        query = str(item.get("query") or "")
        creator_key = str(item.get("_creator_key") or "")
        series_key = str(item.get("_series_key") or "")
        if not asset_id or asset_id in selected_ids:
            return
        if require_new_query and query in used_queries:
            return
        if require_new_creator and creator_key and creator_key in used_creators:
            return
        if require_new_series and series_key and series_key in used_series:
            return
        selected_ids.add(asset_id)
        used_queries.add(query)
        if creator_key:
            used_creators.add(creator_key)
        if series_key:
            used_series.add(series_key)
        public_item = dict(item)
        public_item.pop("_creator_key", None)
        public_item.pop("_series_key", None)
        selected.append(public_item)

    # First pass is intentionally strict: different search intent and creator/source.
    diversity_passes = (
        (True, True, True),
        (True, False, True),
        (False, True, True),
        (False, False, True),
        (False, False, False),
    )
    for require_new_query, require_new_creator, require_new_series in diversity_passes:
        for item in candidates:
            try_add(
                item,
                require_new_query=require_new_query,
                require_new_creator=require_new_creator,
                require_new_series=require_new_series,
            )
            if len(selected) >= limit:
                return selected
    return selected


def resolve_pexels_prompt(payload: dict[str, Any]) -> str:
    candidates = [
        str(payload.get("background_prompt") or "").strip(),
        str(payload.get("text") or "").strip(),
        str(payload.get("idea") or "").strip(),
    ]
    for candidate in candidates:
        if has_useful_pexels_prompt(candidate):
            return candidate
    return candidates[0] or candidates[1] or candidates[2]


def has_useful_pexels_prompt(value: str) -> bool:
    text = value.strip()
    if len(text) < 3:
        return False
    if re.fullmatch(r"[A-Za-z]", text):
        return False
    if re.fullmatch(r"[\W_]+", text):
        return False
    return True


def sanitize_pexels_queries(queries: list[str]) -> list[str]:
    cleaned: list[str] = []
    for query in queries:
        compact = " ".join(str(query or "").replace(",", " ").split()[:8])
        if not has_useful_pexels_prompt(compact):
            continue
        if compact not in cleaned:
            cleaned.append(compact)
    return cleaned


def safe_pexels_get(
    requests_module: Any,
    url: str,
    api_key: str,
    params: dict[str, Any],
) -> Any | None:
    try:
        response = requests_module.get(
            url,
            headers={"Authorization": api_key},
            params=params,
            timeout=60,
        )
        if response.status_code in {500, 502, 503, 504}:
            return None
        return response
    except Exception:
        return None


def build_grouped_pexels_queries(prompt: str) -> list[str]:
    scene_mapping = {
        "打篮球": ["basketball game", "indoor basketball court"],
        "篮球": ["basketball court", "basketball practice"],
        "球场": ["basketball court", "sports court"],
        "教室": ["classroom interior", "empty classroom"],
        "课堂": ["classroom students", "classroom lesson"],
        "走廊": ["school hallway", "corridor walking"],
        "廊道": ["corridor", "hallway"],
        "校园": ["school campus", "campus walkway"],
        "学校": ["school building", "school campus"],
        "学生": ["students walking", "students classroom"],
        "便利店": ["convenience store interior", "storefront night"],
        "咖啡": ["coffee shop", "coffee cup close up"],
        "雨夜": ["rainy night street", "rainy window reflections"],
        "霓虹": ["neon lights", "neon reflections"],
    }
    queries: list[str] = []
    for source, candidates in scene_mapping.items():
        if source in prompt:
            queries.extend(candidates)
    if not queries and all(ord(char) < 128 for char in prompt.strip()):
        for chunk in re.split(r"[,;/，、。\\n]+", prompt):
            compact = " ".join(chunk.strip().split()[:8])
            if compact:
                queries.append(compact)
    deduped: list[str] = []
    for query in queries:
        compact = " ".join(query.replace(",", " ").split()[:8])
        if has_useful_pexels_prompt(compact) and compact not in deduped:
            deduped.append(compact)
    return deduped[:8]


def build_pexels_series_key(value: Any) -> str:
    text = str(value or "").lower()
    text = re.sub(r"https?://[^/]+/", "", text)
    text = re.sub(r"\\b(photo|video|videos|free|stock|hd|4k|pexels)\\b", " ", text)
    tokens = [
        token for token in re.split(r"[^a-z0-9]+", text)
        if token and not token.isdigit() and len(token) > 2
    ]
    return "-".join(tokens[:5])


def prepare_selected_background(
    payload: dict[str, Any],
    output_dir: Path,
    progress: Callable[[str], None] | None = None,
) -> None:
    raw_assets = str(payload.get("selected_background_assets") or "").strip()
    if not raw_assets:
        return
    try:
        assets = json.loads(raw_assets)
    except json.JSONDecodeError as exc:
        raise ValueError("已选背景素材数据格式错误。") from exc
    if not isinstance(assets, list) or not assets:
        return

    manifest_items: list[dict[str, str]] = []
    for index, item in enumerate(assets, start=1):
        if not isinstance(item, dict):
            continue
        asset_url = str(item.get("asset_url") or "").strip()
        asset_kind = str(item.get("kind") or "").strip()
        asset_label = str(item.get("label") or item.get("asset_id") or asset_kind).strip()
        if not asset_url or asset_kind not in {"image", "video"}:
            continue
        suffix = ".mp4" if asset_kind == "video" else ".jpg"
        asset_path = output_dir / f"selected_background_{index:02d}{suffix}"
        if progress:
            progress(f"[步骤] 正在下载已选背景素材 {index}/{len(assets)} ({asset_kind})：{asset_label}\n")
        local_asset_path = Path(asset_url).expanduser()
        if local_asset_path.exists():
            shutil.copy2(local_asset_path, asset_path)
        else:
            pipeline_script.download_file(
                asset_url,
                asset_path,
                headers={
                    "User-Agent": "Mozilla/5.0",
                    "Referer": "https://www.pexels.com/",
                },
            )
        if progress and asset_path.exists():
            progress(f"[步骤] 背景素材 {index}/{len(assets)} 下载完成，大小约 {format_file_size(asset_path.stat().st_size)}。\n")
        manifest_items.append(
            {
                "background_video": str(asset_path) if asset_kind == "video" else "",
                "background_image": str(asset_path) if asset_kind == "image" else "",
            }
        )

    if not manifest_items:
        return

    payload["background_mode"] = "manual"
    payload["background_image"] = manifest_items[0]["background_image"]
    payload["background_video"] = manifest_items[0]["background_video"]
    manifest_path = output_dir / "storyboard_backgrounds_manifest.json"
    manifest_path.write_text(json.dumps(manifest_items, ensure_ascii=False, indent=2), encoding="utf-8")
    payload["storyboard_backgrounds_manifest"] = str(manifest_path)


def format_file_size(byte_count: int) -> str:
    size = float(byte_count)
    for unit in ("B", "KB", "MB", "GB"):
        if size < 1024 or unit == "GB":
            return f"{size:.1f}{unit}"
        size /= 1024
    return f"{size:.1f}GB"


def detect_upload_media_kind(content_type: str, filename: str) -> str:
    lower_type = content_type.lower()
    suffix = Path(filename).suffix.lower()
    if lower_type.startswith("image/") or suffix in {".jpg", ".jpeg", ".png", ".webp"}:
        return "image"
    if lower_type.startswith("video/") or suffix in {".mp4", ".mov", ".m4v", ".webm"}:
        return "video"
    if lower_type.startswith("audio/") or suffix in {".mp3", ".wav", ".m4a", ".aac", ".flac"}:
        return "audio"
    raise ValueError("暂不支持这个文件类型，请上传图片、视频或音频文件。")


def default_suffix_for_media(media_kind: str) -> str:
    return {
        "image": ".jpg",
        "video": ".mp4",
        "audio": ".mp3",
    }.get(media_kind, ".bin")


def run_job(job: WebJob) -> None:
    env = os.environ.copy()
    output_dir = Path(job.output_dir)
    stdout_log_path = output_dir / "stdout.log"
    with JOB_LOCK:
        job.status = "running"
        job.started_at = time.time()
        job.log += "[步骤] 任务已进入后台队列，正在准备素材...\n"

    def append_job_log(message: str) -> None:
        with JOB_LOCK:
            job.log += message

    try:
        prepare_selected_background(job.payload, output_dir, progress=append_job_log)
        command = build_command(job.payload, output_dir)
        with JOB_LOCK:
            job.log += f"$ {' '.join(command)}\n"
    except Exception as exc:
        with JOB_LOCK:
            job.status = "failed"
            job.finished_at = time.time()
            job.log += f"[错误] 任务准备失败: {exc}\n"
        return

    process = subprocess.Popen(
        command,
        cwd=str(BASE_DIR),
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        env=env,
    )
    job.process = process
    output_lines: list[str] = []
    assert process.stdout is not None
    with stdout_log_path.open("w", encoding="utf-8") as stdout_handle:
        for line in process.stdout:
            output_lines.append(line)
            stdout_handle.write(line)
            stdout_handle.flush()
            with JOB_LOCK:
                job.log = "".join(output_lines)
    return_code = process.wait()

    final_video_path = ""
    try:
        last_json = extract_last_json("".join(output_lines))
        if isinstance(last_json, dict):
            final_video_path = str(last_json.get("final_video_path") or "")
    except Exception:
        final_video_path = ""

    with JOB_LOCK:
        job.final_video_path = final_video_path
        job.status = "success" if return_code == 0 else "failed"
        job.finished_at = time.time()


def extract_last_json(output: str) -> dict[str, Any] | None:
    end = output.rfind("}")
    start = output.rfind("{", 0, end + 1)
    while start != -1 and end != -1 and start < end:
        candidate = output[start : end + 1]
        try:
            return json.loads(candidate)
        except json.JSONDecodeError:
            start = output.rfind("{", 0, start)
    return None


class AppHandler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path == "/":
            self.respond_html()
            return
        if parsed.path == "/api/jobs":
            self.respond_json(self.list_jobs())
            return
        if parsed.path == "/api/config-status":
            self.respond_json(config_status())
            return
        if parsed.path == "/api/file":
            self.respond_file(parsed.query)
            return
        self.respond_json({"error": "Not found"}, status=HTTPStatus.NOT_FOUND)

    def do_POST(self) -> None:
        parsed = urlparse(self.path)
        try:
            if parsed.path == "/api/upload":
                self.handle_upload()
                return
            length = int(self.headers.get("Content-Length", "0"))
            raw = self.rfile.read(length).decode("utf-8")
            payload = json.loads(raw) if raw else {}
            if parsed.path == "/api/jobs":
                job = self.create_job(payload)
                self.respond_json(job.to_dict(), status=HTTPStatus.CREATED)
                return
            if parsed.path == "/api/pexels-preview":
                candidates = search_pexels_candidates(payload)
                self.respond_json({"candidates": candidates}, status=HTTPStatus.OK)
                return
            if parsed.path == "/api/generate-script":
                result = generate_script_draft(payload)
                self.respond_json(result, status=HTTPStatus.OK)
                return
            if parsed.path == "/api/voice-preview":
                audio_bytes = generate_voice_preview(payload)
                self.send_response(HTTPStatus.OK)
                self.send_header("Content-Type", "audio/mpeg")
                self.send_header("Content-Length", str(len(audio_bytes)))
                self.end_headers()
                self.wfile.write(audio_bytes)
                return
            self.respond_json({"error": "Not found"}, status=HTTPStatus.NOT_FOUND)
        except Exception as exc:
            self.respond_json({"error": str(exc)}, status=HTTPStatus.BAD_REQUEST)

    def handle_upload(self) -> None:
        form = cgi.FieldStorage(
            fp=self.rfile,
            headers=self.headers,
            environ={
                "REQUEST_METHOD": "POST",
                "CONTENT_TYPE": self.headers.get("Content-Type", ""),
            },
        )
        file_item = form["file"] if "file" in form else None
        if file_item is None or not getattr(file_item, "filename", ""):
            raise ValueError("没有收到上传文件。")
        content_type = str(getattr(file_item, "type", "") or "")
        media_kind = detect_upload_media_kind(content_type, file_item.filename)
        upload_dir = OUTPUT_DIR / "_uploads"
        upload_dir.mkdir(parents=True, exist_ok=True)
        suffix = Path(file_item.filename).suffix.lower() or default_suffix_for_media(media_kind)
        output_path = upload_dir / f"{uuid.uuid4().hex[:12]}{suffix}"
        with output_path.open("wb") as handle:
            shutil.copyfileobj(file_item.file, handle)
        self.respond_json(
            {
                "path": str(output_path),
                "media_kind": media_kind,
                "filename": file_item.filename,
                "content_type": content_type,
            }
        )

    def create_job(self, payload: dict[str, Any]) -> WebJob:
        validate_job_payload(payload)
        job_id = uuid.uuid4().hex[:10]
        title = (payload.get("title") or f"web_job_{job_id}").strip()
        output_dir = OUTPUT_DIR / job_id
        output_dir.mkdir(parents=True, exist_ok=True)
        job = WebJob(
            id=job_id,
            title=title,
            status="queued",
            payload=payload,
            output_dir=str(output_dir),
        )
        with JOB_LOCK:
            JOB_STORE[job_id] = job
        thread = threading.Thread(target=run_job, args=(job,), daemon=True)
        thread.start()
        return job

    def list_jobs(self) -> list[dict[str, Any]]:
        with JOB_LOCK:
            jobs = [job.to_dict() for job in reversed(list(JOB_STORE.values()))]
        return jobs

    def respond_html(self) -> None:
        background_config = str(BASE_DIR / "background_webhook_config.example.json")
        content = HTML_PAGE.replace("__BACKGROUND_CONFIG__", background_config)
        data = content.encode("utf-8")
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        try:
            self.wfile.write(data)
        except (BrokenPipeError, ConnectionResetError):
            return

    def respond_json(self, payload: Any, status: HTTPStatus = HTTPStatus.OK) -> None:
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def respond_file(self, query: str) -> None:
        params = parse_qs(query)
        job_id = (params.get("job_id") or [""])[0]
        kind = (params.get("kind") or ["video"])[0]
        should_download = (params.get("download") or ["0"])[0] == "1"
        with JOB_LOCK:
            job = JOB_STORE.get(job_id)
        if not job:
            self.respond_json({"error": "Job not found"}, status=HTTPStatus.NOT_FOUND)
            return
        if kind == "video":
            path = Path(job.final_video_path)
        elif kind == "log":
            path = Path(job.output_dir) / "stdout.log"
        else:
            self.respond_json({"error": "Unsupported file kind"}, status=HTTPStatus.BAD_REQUEST)
            return
        if not path.exists():
            self.respond_json({"error": "File not ready"}, status=HTTPStatus.NOT_FOUND)
            return
        data = path.read_bytes()
        content_type = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(data)))
        if should_download:
            self.send_header("Content-Disposition", f'attachment; filename="{path.name}"')
        self.end_headers()
        try:
            self.wfile.write(data)
        except (BrokenPipeError, ConnectionResetError):
            return

    def log_message(self, format: str, *args: Any) -> None:
        return


def main() -> None:
    port = int(os.getenv("AUTO_DIGIT_WEB_PORT", "8765"))
    server = ThreadingHTTPServer(("127.0.0.1", port), AppHandler)
    print(f"AI 短视频生成平台已启动: http://127.0.0.1:{port}")
    server.serve_forever()


if __name__ == "__main__":
    main()

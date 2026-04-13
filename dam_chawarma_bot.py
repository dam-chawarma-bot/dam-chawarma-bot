#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import logging
import sqlite3
from datetime import datetime, date, timedelta, time
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler,
    MessageHandler, ConversationHandler, filters, ContextTypes
)

TOKEN     = "REMPLACE_PAR_TON_TOKEN"
PATRON_ID = 932787045
DB_PATH   = "dam_chawarma.db"

logging.basicConfig(format="%(asctime)s - %(levelname)s - %(message)s", level=logging.INFO)
logger = logging.getLogger(__name__)

CHOIX_CATEGORIE, CHOIX_PRODUIT, SAISIE_QUANTITE, CHOIX_PAIEMENT = range(4)

CATEGORIES = {
    "🌯 Chawarma": {
        "CHAWARMA (S)": 1000,
        "CHAWARMA (M)": 1500,
        "CHAWARMA (L)": 2000,
    },
    "🍝 Plats": {
        "SPAGUETTI (S)": 500,
        "SPAGUETTI (M)": 1000,
        "INDOMIE": 500,
        "FRITES": 1000,
    },
    "🍮 Desserts": {
        "DEGUE (S)": 300,
        "DEGUE (L)": 500,
    },
    "🥤 Boissons": {
        "YOUKI PLASTIQUE": 400,
        "COCA COLA PLASTIQUE": 300,
        "COCA COLA CANETTE": 350,
        "EAU DE COCO": 450,
        "MALTA": 400,
    },
    "🍺 Bières": {
        "PETITE BENINOISE": 350,
        "DESPERADOS": 600,
        "DOPPEL": 600,
        "FLAG": 600,
        "PILS": 500,
        "BEAUFORT": 600,
    },
}

MODES_PAIEMENT = ["💵 Espèces", "📱 Mobile Money", "💳 Carte"]

# ── BASE DE DONNÉES ───────────────────────────────────────────
def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS ventes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            date TEXT,
            heure TEXT,
            caissier TEXT,
            produit TEXT,
            quantite INTEGER,
            prix_unit INTEGER,
            total INTEGER,
            paiement TEXT
        )
    """)
    conn.commit()
    conn.close()

def save_vente(caissier, produit, quantite, prix_unit, paiement):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    now = datetime.now()
    c.execute("""
        INSERT INTO ventes VALUES (NULL,?,?,?,?,?,?,?,?)
    """, (
        now.strftime("%Y-%m-%d"),
        now.strftime("%H:%M"),
        caissier, produit, quantite,
        prix_unit, quantite * prix_unit, paiement
    ))
    conn.commit()
    conn.close()

def get_rapport_jour(jour):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    c.execute("SELECT SUM(total), SUM(quantite), COUNT(*) FROM ventes WHERE date=?", (jour,))
    total, qte, nb = c.fetchone()
    total = total or 0
    qte = qte or 0
    nb = nb or 0

    c.execute("SELECT produit, SUM(quantite), SUM(total) FROM ventes WHERE date=? GROUP BY produit", (jour,))
    par_produit = c.fetchall()

    c.execute("SELECT paiement, SUM(total) FROM ventes WHERE date=? GROUP BY paiement", (jour,))
    par_paiement = c.fetchall()

    conn.close()

    return {
        "jour": jour,
        "total": total,
        "qte": qte,
        "nb": nb,
        "par_produit": par_produit,
        "par_paiement": par_paiement
    }

def fmt(n):
    return f"{int(n):,}".replace(",", " ") + " FCFA"

# ── CLAVIERS ──────────────────────────────────────────────────
def kb_categories():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(cat, callback_data=f"cat:{cat}")]
        for cat in CATEGORIES
    ])

def kb_produits(cat):
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(f"{n} — {fmt(p)}", callback_data=f"prod:{n}:{p}")]
        for n, p in CATEGORIES[cat].items()
    ])

def kb_paiement():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(m, callback_data=f"pay:{m}")]
        for m in MODES_PAIEMENT
    ])

# ── VENTE ─────────────────────────────────────────────────────
async def vente_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🛒 *Nouvelle vente*\n\nChoisis la catégorie :",
        parse_mode="Markdown",
        reply_markup=kb_categories()
    )
    return CHOIX_CATEGORIE

async def choix_categorie(update: Update, ctx):
    q = update.callback_query
    await q.answer()
    cat = q.data.replace("cat:", "")
    ctx.user_data["categorie"] = cat

    await q.edit_message_text(
        f"Catégorie : {cat}\nChoisis produit :",
        reply_markup=kb_produits(cat)
    )
    return CHOIX_PRODUIT

async def choix_produit(update: Update, ctx):
    q = update.callback_query
    await q.answer()

    _, produit, prix = q.data.split(":")
    ctx.user_data["produit"] = produit
    ctx.user_data["prix"] = int(prix)

    await q.edit_message_text(f"{produit}\nQuantité ?")
    return SAISIE_QUANTITE

async def saisie_quantite(update: Update, ctx):
    qte = int(update.message.text)
    ctx.user_data["quantite"] = qte

    produit = ctx.user_data["produit"]
    prix = ctx.user_data["prix"]
    total = qte * prix

    await update.message.reply_text(
        f"{produit} × {qte}\nTotal : {fmt(total)}\nPaiement ?",
        reply_markup=kb_paiement()
    )
    return CHOIX_PAIEMENT

# 🔥 AVEC BOUTON NOUVELLE VENTE
async def choix_paiement(update: Update, ctx):
    q = update.callback_query
    await q.answer()

    paiement = q.data.replace("pay:", "")
    produit = ctx.user_data["produit"]
    qte = ctx.user_data["quantite"]
    prix = ctx.user_data["prix"]
    total = qte * prix
    caissier = update.effective_user.first_name

    save_vente(caissier, produit, qte, prix, paiement)

    keyboard = [[InlineKeyboardButton("➕ Nouvelle vente", callback_data="new_vente")]]

    await q.edit_message_text(
        f"✅ Vente enregistrée\n\n{produit} × {qte}\n{fmt(total)}",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

    return ConversationHandler.END

async def nouvelle_vente(update: Update, ctx):
    q = update.callback_query
    await q.answer()

    await q.message.reply_text(
        "🛒 Nouvelle vente\nChoisis la catégorie :",
        reply_markup=kb_categories()
    )

    return CHOIX_CATEGORIE

# ── RAPPORT AUTO ──────────────────────────────────────────────
async def rapport_auto(ctx: ContextTypes.DEFAULT_TYPE):
    now = datetime.now()

    if now.hour < 5:
        jour = (now - timedelta(days=1)).strftime("%Y-%m-%d")
    else:
        jour = now.strftime("%Y-%m-%d")

    r = get_rapport_jour(jour)

    if r["nb"] == 0:
        message = f"Aucune vente pour {jour}"
    else:
        produits = "\n".join(f"{n} x{q} = {fmt(t)}" for n, q, t in r["par_produit"])
        paiements = "\n".join(f"{m} : {fmt(t)}" for m, t in r["par_paiement"])

        message = (
            f"📊 RAPPORT {jour}\n\n"
            f"CA : {fmt(r['total'])}\n"
            f"Ventes : {r['nb']}\n\n"
            f"{produits}\n\n{paiements}"
        )

    await ctx.bot.send_message(chat_id=PATRON_ID, text=message)

# ── MAIN ──────────────────────────────────────────────────────
def main():
    init_db()
    app = Application.builder().token(TOKEN).build()

    conv = ConversationHandler(
        entry_points=[CommandHandler("vente", vente_start)],
        states={
            CHOIX_CATEGORIE: [CallbackQueryHandler(choix_categorie)],
            CHOIX_PRODUIT: [CallbackQueryHandler(choix_produit)],
            SAISIE_QUANTITE: [MessageHandler(filters.TEXT, saisie_quantite)],
            CHOIX_PAIEMENT: [CallbackQueryHandler(choix_paiement)],
        },
        fallbacks=[],
    )

    app.add_handler(conv)
    app.add_handler(CallbackQueryHandler(nouvelle_vente, pattern="new_vente"))

    # 🔥 RAPPORT AUTOMATIQUE À 02H30
    app.job_queue.run_daily(
        rapport_auto,
        time=time(hour=2, minute=30)
    )

    print("Bot lancé 🚀")
    app.run_polling()

if __name__ == "__main__":
    main()

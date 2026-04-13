#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
DAM CHAWARMA - Bot Telegram de suivi des ventes
"""

import logging
import sqlite3
import os
from datetime import datetime, date
from telegram import Update, ReplyKeyboardMarkup, ReplyKeyboardRemove
from telegram.ext import (
    Application, CommandHandler, MessageHandler,
    ConversationHandler, filters, ContextTypes
)

# ── CONFIG ────────────────────────────────────────────────────
TOKEN      = "8736305442:AAHr2vHglNqSdY3am3KrFt2qOaIU4KcKyxY"
PATRON_ID  = 932787045
DB_PATH    = "dam_chawarma.db"

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# ── ÉTATS CONVERSATION ────────────────────────────────────────
PRODUIT, QUANTITE, PRIX, PAIEMENT = range(4)

# ── MENU ──────────────────────────────────────────────────────
MENU = {
    "CHAWARMA (S)": 1000,
    "CHAWARMA (M)": 1500,
    "CHAWARMA (L)": 2000,
    "SPAGUETTI (S)": 500,
    "SPAGUETTI (M)": 1000,
    "INDOMIE": 500,
    "FRITES": 1000,
    "DEGUE (S)": 300,
    "DEGUE (L)": 500,
    "YOUKI PLASTIQUE": 400,
    "COCA COLA PLASTIQUE": 300,
    "COCA COLA CANETTE": 350,
    "PETITE BENINOISE": 350,
    "DESPERADOS": 600,
    "DOPPEL": 600,
    "FLAG": 600,
    "MALTA": 400,
    "PILS": 500,
    "BEAUFORT": 600,
    "EAU DE COCO": 450,
}

MODES_PAIEMENT = ["Espèces", "Mobile Money", "Carte"]

# ── BASE DE DONNÉES ───────────────────────────────────────────
def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS ventes (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            date        TEXT NOT NULL,
            heure       TEXT NOT NULL,
            caissier    TEXT NOT NULL,
            produit     TEXT NOT NULL,
            quantite    INTEGER NOT NULL,
            prix_unit   INTEGER NOT NULL,
            total       INTEGER NOT NULL,
            paiement    TEXT NOT NULL
        )
    """)
    conn.commit()
    conn.close()

def save_vente(caissier, produit, quantite, prix_unit, paiement):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    now = datetime.now()
    c.execute("""
        INSERT INTO ventes (date, heure, caissier, produit, quantite, prix_unit, total, paiement)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        now.strftime("%Y-%m-%d"),
        now.strftime("%H:%M"),
        caissier,
        produit,
        quantite,
        prix_unit,
        quantite * prix_unit,
        paiement
    ))
    conn.commit()
    conn.close()

def get_rapport_jour(jour=None):
    if not jour:
        jour = date.today().strftime("%Y-%m-%d")
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    # Total général
    c.execute("SELECT SUM(total), SUM(quantite), COUNT(*) FROM ventes WHERE date=?", (jour,))
    total, qte_total, nb_tickets = c.fetchone()
    total = total or 0
    qte_total = qte_total or 0
    nb_tickets = nb_tickets or 0
    # Par produit
    c.execute("""
        SELECT produit, SUM(quantite), SUM(total)
        FROM ventes WHERE date=?
        GROUP BY produit ORDER BY SUM(total) DESC
    """, (jour,))
    par_produit = c.fetchall()
    # Par mode paiement
    c.execute("""
        SELECT paiement, SUM(total)
        FROM ventes WHERE date=?
        GROUP BY paiement
    """, (jour,))
    par_paiement = c.fetchall()
    # Par caissier
    c.execute("""
        SELECT caissier, SUM(total), COUNT(*)
        FROM ventes WHERE date=?
        GROUP BY caissier
    """, (jour,))
    par_caissier = c.fetchall()
    conn.close()
    return {
        "jour": jour,
        "total": total,
        "qte_total": qte_total,
        "nb_tickets": nb_tickets,
        "par_produit": par_produit,
        "par_paiement": par_paiement,
        "par_caissier": par_caissier,
    }

def get_last_ventes(n=5):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("""
        SELECT heure, caissier, produit, quantite, total, paiement
        FROM ventes ORDER BY id DESC LIMIT ?
    """, (n,))
    rows = c.fetchall()
    conn.close()
    return rows

# ── HELPERS ───────────────────────────────────────────────────
def fmt(n):
    return f"{int(n):,}".replace(",", " ") + " FCFA"

def is_patron(user_id):
    return user_id == PATRON_ID

def keyboard_produits():
    items = list(MENU.keys())
    rows = [items[i:i+2] for i in range(0, len(items), 2)]
    return ReplyKeyboardMarkup(rows, resize_keyboard=True, one_time_keyboard=True)

def keyboard_paiement():
    return ReplyKeyboardMarkup([MODES_PAIEMENT], resize_keyboard=True, one_time_keyboard=True)

# ── COMMANDES GÉNÉRALES ───────────────────────────────────────
async def start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    uid  = user.id
    nom  = user.first_name

    if is_patron(uid):
        msg = (
            f"👑 Bienvenue patron *{nom}* !\n\n"
            "🌯 *DAM CHAWARMA — Bot de suivi des ventes*\n\n"
            "Vos commandes :\n"
            "🛒 /vente — Enregistrer une vente\n"
            "📊 /rapport — Rapport du jour\n"
            "🏆 /top — Top produits du jour\n"
            "💰 /solde — Chiffre d'affaires en temps réel\n"
            "📋 /dernières — 5 dernières ventes\n"
            "❓ /aide — Aide"
        )
    else:
        msg = (
            f"👋 Bonjour *{nom}* !\n\n"
            "🌯 *DAM CHAWARMA — Saisie des ventes*\n\n"
            "Commandes disponibles :\n"
            "🛒 /vente — Enregistrer une vente\n"
            "📋 /dernieres — Mes dernières ventes\n"
            "❓ /aide — Aide"
        )
    await update.message.reply_text(msg, parse_mode="Markdown")

async def aide(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "📖 *Guide d'utilisation*\n\n"
        "1️⃣ Tape /vente\n"
        "2️⃣ Choisis le produit dans le menu\n"
        "3️⃣ Entre la quantité\n"
        "4️⃣ Confirme ou modifie le prix\n"
        "5️⃣ Choisis le mode de paiement\n\n"
        "✅ La vente est enregistrée et le patron est notifié !",
        parse_mode="Markdown"
    )

# ── CONVERSATION : SAISIR UNE VENTE ──────────────────────────
async def vente_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🛒 *Nouvelle vente*\n\nChoisis le produit :",
        parse_mode="Markdown",
        reply_markup=keyboard_produits()
    )
    return PRODUIT

async def vente_produit(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    produit = update.message.text.strip().upper()
    # Cherche correspondance
    match = None
    for p in MENU:
        if produit == p.upper():
            match = p
            break
    if not match:
        # Recherche partielle
        for p in MENU:
            if produit in p.upper():
                match = p
                break
    if not match:
        await update.message.reply_text(
            "❌ Produit non reconnu. Choisis dans la liste :",
            reply_markup=keyboard_produits()
        )
        return PRODUIT

    ctx.user_data["produit"] = match
    ctx.user_data["prix_suggest"] = MENU[match]
    await update.message.reply_text(
        f"✅ Produit : *{match}*\n\n🔢 Quelle quantité ?",
        parse_mode="Markdown",
        reply_markup=ReplyKeyboardRemove()
    )
    return QUANTITE

async def vente_quantite(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    try:
        qte = int(update.message.text.strip())
        if qte <= 0: raise ValueError
    except ValueError:
        await update.message.reply_text("❌ Entre un nombre valide (ex: 1, 2, 3...)")
        return QUANTITE

    ctx.user_data["quantite"] = qte
    prix = ctx.user_data["prix_suggest"]
    await update.message.reply_text(
        f"💰 Prix unitaire :\n"
        f"Prix catalogue : *{fmt(prix)}*\n\n"
        f"Tape le prix ou envoie *OK* pour confirmer {fmt(prix)}",
        parse_mode="Markdown"
    )
    return PRIX

async def vente_prix(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    txt = update.message.text.strip().upper()
    if txt == "OK":
        prix = ctx.user_data["prix_suggest"]
    else:
        try:
            prix = int(txt.replace(" ", "").replace("FCFA", ""))
            if prix <= 0: raise ValueError
        except ValueError:
            await update.message.reply_text("❌ Entre un prix valide ou tape OK")
            return PRIX

    ctx.user_data["prix"] = prix
    qte   = ctx.user_data["quantite"]
    total = qte * prix
    await update.message.reply_text(
        f"💳 Mode de paiement ?\n\n"
        f"Sous-total : *{fmt(total)}*",
        parse_mode="Markdown",
        reply_markup=keyboard_paiement()
    )
    return PAIEMENT

async def vente_paiement(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    paiement = update.message.text.strip()
    if paiement not in MODES_PAIEMENT:
        await update.message.reply_text(
            "❌ Choisis parmi les options :",
            reply_markup=keyboard_paiement()
        )
        return PAIEMENT

    produit  = ctx.user_data["produit"]
    quantite = ctx.user_data["quantite"]
    prix     = ctx.user_data["prix"]
    total    = quantite * prix
    caissier = update.effective_user.first_name

    save_vente(caissier, produit, quantite, prix, paiement)

    # Confirmation au caissier
    await update.message.reply_text(
        f"✅ *Vente enregistrée !*\n\n"
        f"🍽️ {produit}\n"
        f"📦 Quantité : {quantite}\n"
        f"💰 Prix unit : {fmt(prix)}\n"
        f"💵 Total : *{fmt(total)}*\n"
        f"💳 Paiement : {paiement}\n"
        f"👤 Caissier : {caissier}\n"
        f"🕐 {datetime.now().strftime('%H:%M')}",
        parse_mode="Markdown",
        reply_markup=ReplyKeyboardRemove()
    )

    # Notification au patron
    if update.effective_user.id != PATRON_ID:
        try:
            await ctx.bot.send_message(
                chat_id=PATRON_ID,
                text=(
                    f"🔔 *Nouvelle vente !*\n\n"
                    f"🍽️ {produit} × {quantite}\n"
                    f"💵 *{fmt(total)}*\n"
                    f"💳 {paiement}\n"
                    f"👤 {caissier}\n"
                    f"🕐 {datetime.now().strftime('%H:%M')}"
                ),
                parse_mode="Markdown"
            )
        except Exception as e:
            logger.warning(f"Notification patron échouée : {e}")

    return ConversationHandler.END

async def vente_annuler(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "❌ Saisie annulée.",
        reply_markup=ReplyKeyboardRemove()
    )
    return ConversationHandler.END

# ── COMMANDES PATRON ──────────────────────────────────────────
async def rapport(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    r = get_rapport_jour()

    if r["nb_tickets"] == 0:
        await update.message.reply_text("📊 Aucune vente enregistrée aujourd'hui.")
        return

    # Par produit
    lignes_produits = ""
    for nom, qte, total in r["par_produit"]:
        lignes_produits += f"  • {nom} × {qte} = {fmt(total)}\n"

    # Par paiement
    lignes_paiement = ""
    for mode, total in r["par_paiement"]:
        lignes_paiement += f"  • {mode} : {fmt(total)}\n"

    # Par caissier
    lignes_caissier = ""
    for caissier, total, nb in r["par_caissier"]:
        lignes_caissier += f"  • {caissier} : {fmt(total)} ({nb} ventes)\n"

    msg = (
        f"📊 *RAPPORT DU JOUR — {r['jour']}*\n"
        f"{'─'*30}\n\n"
        f"💵 CA TOTAL : *{fmt(r['total'])}*\n"
        f"🎫 Tickets : {r['nb_tickets']}\n"
        f"📦 Articles vendus : {r['qte_total']}\n\n"
        f"🍽️ *PAR PRODUIT :*\n{lignes_produits}\n"
        f"💳 *PAR PAIEMENT :*\n{lignes_paiement}\n"
        f"👤 *PAR CAISSIER :*\n{lignes_caissier}"
    )
    await update.message.reply_text(msg, parse_mode="Markdown")

async def solde(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    r = get_rapport_jour()
    heure = datetime.now().strftime("%H:%M")
    await update.message.reply_text(
        f"💰 *CHIFFRE D'AFFAIRES EN TEMPS RÉEL*\n\n"
        f"📅 {r['jour']}  🕐 {heure}\n\n"
        f"💵 *{fmt(r['total'])}*\n\n"
        f"🎫 {r['nb_tickets']} vente(s) enregistrée(s)",
        parse_mode="Markdown"
    )

async def top(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    r = get_rapport_jour()
    if not r["par_produit"]:
        await update.message.reply_text("🏆 Aucune vente aujourd'hui.")
        return

    medals = ["🥇", "🥈", "🥉", "4️⃣", "5️⃣"]
    lignes = ""
    for i, (nom, qte, total) in enumerate(r["par_produit"][:5]):
        m = medals[i] if i < len(medals) else "▪️"
        lignes += f"{m} {nom}\n   → {qte} vendu(s) | {fmt(total)}\n"

    await update.message.reply_text(
        f"🏆 *TOP PRODUITS — {r['jour']}*\n\n{lignes}",
        parse_mode="Markdown"
    )

async def dernieres(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    rows = get_last_ventes(5)
    if not rows:
        await update.message.reply_text("📋 Aucune vente enregistrée.")
        return

    lignes = ""
    for heure, caissier, produit, qte, total, paiement in rows:
        lignes += f"🕐 {heure} | {produit} ×{qte} = {fmt(total)} ({caissier})\n"

    await update.message.reply_text(
        f"📋 *5 DERNIÈRES VENTES*\n\n{lignes}",
        parse_mode="Markdown"
    )

# ── MAIN ──────────────────────────────────────────────────────
def main():
    init_db()
    app = Application.builder().token(TOKEN).build()

    # Conversation vente
    conv = ConversationHandler(
        entry_points=[CommandHandler("vente", vente_start)],
        states={
            PRODUIT:   [MessageHandler(filters.TEXT & ~filters.COMMAND, vente_produit)],
            QUANTITE:  [MessageHandler(filters.TEXT & ~filters.COMMAND, vente_quantite)],
            PRIX:      [MessageHandler(filters.TEXT & ~filters.COMMAND, vente_prix)],
            PAIEMENT:  [MessageHandler(filters.TEXT & ~filters.COMMAND, vente_paiement)],
        },
        fallbacks=[CommandHandler("annuler", vente_annuler)],
    )

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("aide", aide))
    app.add_handler(conv)
    app.add_handler(CommandHandler("rapport", rapport))
    app.add_handler(CommandHandler("solde", solde))
    app.add_handler(CommandHandler("top", top))
    app.add_handler(CommandHandler("dernieres", dernieres))

    logger.info("🌯 DAM CHAWARMA Bot démarré !")
    app.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()

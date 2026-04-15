#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
DAM CHAWARMA - Bot Telegram v5
  - Rapport affiche d'abord le jour précédent puis le jour actuel
  - Bouton 🔴 Enregistrer une nouvelle vente après toute annulation ou vente
"""

import logging
import sqlite3
from datetime import datetime, date, timedelta
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler,
    MessageHandler, ConversationHandler, filters, ContextTypes
)

TOKEN     = "8736305442:AAHr2vHglNqSdY3am3KrFt2qOaIU4KcKyxY"
PATRON_ID = 932787045
DB_PATH   = "dam_chawarma.db"

logging.basicConfig(format="%(asctime)s - %(levelname)s - %(message)s", level=logging.INFO)
logger = logging.getLogger(__name__)

# ── ÉTATS ─────────────────────────────────────────────────────
CHOIX_CATEGORIE, CHOIX_PRODUIT, SAISIE_QUANTITE, CHOIX_PAIEMENT = range(4)

# ── MENU COMPLET ──────────────────────────────────────────────
CATEGORIES = {
    "🌯 Chawarma": {
        "CHAWARMA (S)": 1000,
        "CHAWARMA (M)": 1500,
        "CHAWARMA (P)": 2000,
    },
    "🍝 Plats": {
        "SPAGUETTI (S)": 500,
        "SPAGUETTI (P)": 1000,
        "INDOMIE": 500,
        "FRITES": 1000,
    },
    "🍮 Desserts": {
        "DEGUE (S)": 300,
        "DEGUE (S) emporté": 350,
        "DEGUE (P)": 500,
        "DEGUE (P) emporté": 500,
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
        "PETITE CHIL": 350,
        "DESPERADOS": 600,
        "DOPPEL": 600,
        "FLAG": 600,
        "PILS": 500,
        "BEAUFORT": 600,
    },
    "💳 EMBALLAGES ET DIVERS": {
        "PLAT JETABLE": 100,
        "VERRE JETABLE": 50,
        "OEUF": 100,
        "SAUCISSE": 100,
        "MAYONNAISE": 100,
    },
}

MODES_PAIEMENT = ["💵 Espèces", "📱 Mobile Money"]

# ── BOUTON RÉUTILISABLE ───────────────────────────────────────
def kb_nouvelle_vente():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🔴 Enregistrer une nouvelle vente", callback_data="nouvelle_vente")]
    ])

# ── BASE DE DONNÉES ───────────────────────────────────────────
def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS ventes (
            id        INTEGER PRIMARY KEY AUTOINCREMENT,
            date      TEXT NOT NULL,
            heure     TEXT NOT NULL,
            caissier  TEXT NOT NULL,
            produit   TEXT NOT NULL,
            quantite  INTEGER NOT NULL,
            prix_unit INTEGER NOT NULL,
            total     INTEGER NOT NULL,
            paiement  TEXT NOT NULL
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
    """, (now.strftime("%Y-%m-%d"), now.strftime("%H:%M"),
          caissier, produit, quantite, prix_unit, quantite * prix_unit, paiement))
    conn.commit()
    conn.close()

def get_rapport_jour(jour=None):
    if not jour:
        jour = date.today().strftime("%Y-%m-%d")
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT SUM(total), SUM(quantite), COUNT(*) FROM ventes WHERE date=?", (jour,))
    total, qte, nb = c.fetchone()
    total = total or 0; qte = qte or 0; nb = nb or 0
    c.execute("SELECT produit, SUM(quantite), SUM(total) FROM ventes WHERE date=? GROUP BY produit ORDER BY SUM(total) DESC", (jour,))
    par_produit = c.fetchall()
    c.execute("SELECT paiement, SUM(total) FROM ventes WHERE date=? GROUP BY paiement", (jour,))
    par_paiement = c.fetchall()
    c.execute("SELECT caissier, SUM(total), COUNT(*) FROM ventes WHERE date=? GROUP BY caissier", (jour,))
    par_caissier = c.fetchall()
    conn.close()
    return {"jour": jour, "total": total, "qte": qte, "nb": nb,
            "par_produit": par_produit, "par_paiement": par_paiement, "par_caissier": par_caissier}

def get_last_ventes(n=5):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT heure, caissier, produit, quantite, total, paiement FROM ventes ORDER BY id DESC LIMIT ?", (n,))
    rows = c.fetchall()
    conn.close()
    return rows

def fmt(n): return f"{int(n):,}".replace(",", " ") + " FCFA"

def formater_rapport(r, titre_emoji="📊"):
    """Formate un rapport en texte prêt à envoyer."""
    if r["nb"] == 0:
        return (
            f"{titre_emoji} *RAPPORT — {r['jour']}*\n{'─'*28}\n\n"
            f"_(Aucune vente ce jour)_"
        )
    lignes_p   = "".join(f"  • {n} ×{q} = {fmt(t)}\n" for n, q, t in r["par_produit"])
    lignes_pay = "".join(f"  • {m} : {fmt(t)}\n" for m, t in r["par_paiement"])
    lignes_c   = "".join(f"  • {c} : {fmt(t)} ({n} ventes)\n" for c, t, n in r["par_caissier"])
    return (
        f"{titre_emoji} *RAPPORT — {r['jour']}*\n{'─'*28}\n\n"
        f"💵 CA TOTAL : *{fmt(r['total'])}*\n"
        f"🎫 Tickets : {r['nb']}\n"
        f"📦 Articles : {r['qte']}\n\n"
        f"🍽️ *PAR PRODUIT :*\n{lignes_p}\n"
        f"💳 *PAR PAIEMENT :*\n{lignes_pay}\n"
        f"👤 *PAR CAISSIER :*\n{lignes_c}"
    )

# ── KEYBOARDS ─────────────────────────────────────────────────
def kb_categories():
    buttons = [[InlineKeyboardButton(cat, callback_data=f"cat:{cat}")]
               for cat in CATEGORIES.keys()]
    buttons.append([InlineKeyboardButton("❌ Annuler", callback_data="annuler")])
    return InlineKeyboardMarkup(buttons)

def kb_produits(categorie):
    produits = CATEGORIES.get(categorie, {})
    buttons = []
    for nom, prix in produits.items():
        buttons.append([InlineKeyboardButton(
            f"{nom}  —  {fmt(prix)}", callback_data=f"prod:{nom}:{prix}"
        )])
    buttons.append([InlineKeyboardButton("⬅️ Retour", callback_data="retour_cat")])
    buttons.append([InlineKeyboardButton("❌ Annuler", callback_data="annuler")])
    return InlineKeyboardMarkup(buttons)

def kb_paiement():
    buttons = [[InlineKeyboardButton(m, callback_data=f"pay:{m}")] for m in MODES_PAIEMENT]
    buttons.append([InlineKeyboardButton("❌ Annuler", callback_data="annuler")])
    return InlineKeyboardMarkup(buttons)

# ── COMMANDES ─────────────────────────────────────────────────
async def start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    nom = update.effective_user.first_name
    uid = update.effective_user.id
    if uid == PATRON_ID:
        msg = (f"👑 Bienvenue patron *{nom}* !\n\n"
               "🌯 *DAM CHAWARMA — Bot de suivi des ventes*\n\n"
               "Vos commandes :\n"
               "🛒 /vente — Enregistrer une vente\n"
               "📊 /rapport — Rapport J-1 + Rapport du jour\n"
               "🏆 /top — Top produits\n"
               "💰 /solde — CA en temps réel\n"
               "📋 /dernieres — 5 dernières ventes\n"
               "❓ /aide — Aide")
    else:
        msg = (f"👋 Bonjour *{nom}* !\n\n"
               "🌯 *DAM CHAWARMA*\n\n"
               "Tape /vente pour enregistrer une vente\n"
               "Tape /aide pour de l'aide")
    await update.message.reply_text(msg, parse_mode="Markdown")

async def aide(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "📖 *Comment saisir une vente :*\n\n"
        "1️⃣ Tape /vente\n"
        "2️⃣ Choisis la *catégorie* (Chawarma, Plats...)\n"
        "3️⃣ Choisis le *produit* — le prix s'affiche automatiquement\n"
        "4️⃣ Tape la *quantité*\n"
        "5️⃣ Choisis le *mode de paiement*\n"
        "6️⃣ Confirme ✅\n\n"
        "C'est tout ! 🎉", parse_mode="Markdown")

# ── CONVERSATION VENTE ────────────────────────────────────────
async def vente_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🛒 *Nouvelle vente*\n\nChoisis la catégorie :",
        parse_mode="Markdown",
        reply_markup=kb_categories()
    )
    return CHOIX_CATEGORIE

async def choix_categorie(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if query.data == "annuler":
        await query.edit_message_text(
            "❌ Vente annulée.",
            reply_markup=kb_nouvelle_vente()
        )
        return ConversationHandler.END

    categorie = query.data.replace("cat:", "")
    ctx.user_data["categorie"] = categorie

    await query.edit_message_text(
        f"🛒 Catégorie : *{categorie}*\n\nChoisis le produit :",
        parse_mode="Markdown",
        reply_markup=kb_produits(categorie)
    )
    return CHOIX_PRODUIT

async def choix_produit(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if query.data == "annuler":
        await query.edit_message_text(
            "❌ Vente annulée.",
            reply_markup=kb_nouvelle_vente()
        )
        return ConversationHandler.END

    if query.data == "retour_cat":
        await query.edit_message_text(
            "🛒 *Nouvelle vente*\n\nChoisis la catégorie :",
            parse_mode="Markdown",
            reply_markup=kb_categories()
        )
        return CHOIX_CATEGORIE

    _, produit, prix = query.data.split(":")
    ctx.user_data["produit"] = produit
    ctx.user_data["prix"] = int(prix)

    await query.edit_message_text(
        f"✅ *{produit}*\n"
        f"💰 Prix : *{fmt(int(prix))}*\n\n"
        f"🔢 Combien d'unités vendues ?",
        parse_mode="Markdown"
    )
    return SAISIE_QUANTITE

async def saisie_quantite(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    try:
        qte = int(update.message.text.strip())
        if qte <= 0: raise ValueError
    except ValueError:
        await update.message.reply_text("❌ Entre un nombre valide (1, 2, 3...)")
        return SAISIE_QUANTITE

    ctx.user_data["quantite"] = qte
    produit = ctx.user_data["produit"]
    prix    = ctx.user_data["prix"]
    total   = qte * prix

    await update.message.reply_text(
        f"💳 *Mode de paiement ?*\n\n"
        f"📦 {produit} × {qte}\n"
        f"💵 Total : *{fmt(total)}*",
        parse_mode="Markdown",
        reply_markup=kb_paiement()
    )
    return CHOIX_PAIEMENT

async def choix_paiement(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if query.data == "annuler":
        await query.edit_message_text(
            "❌ Vente annulée.",
            reply_markup=kb_nouvelle_vente()
        )
        return ConversationHandler.END

    paiement = query.data.replace("pay:", "")
    produit  = ctx.user_data["produit"]
    qte      = ctx.user_data["quantite"]
    prix     = ctx.user_data["prix"]
    total    = qte * prix
    caissier = update.effective_user.first_name

    save_vente(caissier, produit, qte, prix, paiement)

    await query.edit_message_text(
        f"✅ *Vente enregistrée !*\n\n"
        f"🍽️ {produit}\n"
        f"📦 Quantité : {qte}\n"
        f"💰 Prix unit : {fmt(prix)}\n"
        f"💵 *Total : {fmt(total)}*\n"
        f"💳 {paiement}\n"
        f"👤 {caissier}\n"
        f"🕐 {datetime.now().strftime('%H:%M')}",
        parse_mode="Markdown",
        reply_markup=kb_nouvelle_vente()
    )

    # Notification patron
    if update.effective_user.id != PATRON_ID:
        try:
            await ctx.bot.send_message(
                chat_id=PATRON_ID,
                text=(f"🔔 *Nouvelle vente !*\n\n"
                      f"🍽️ {produit} × {qte}\n"
                      f"💵 *{fmt(total)}*\n"
                      f"💳 {paiement}\n"
                      f"👤 {caissier}\n"
                      f"🕐 {datetime.now().strftime('%H:%M')}"),
                parse_mode="Markdown"
            )
        except Exception as e:
            logger.warning(f"Notif patron échouée : {e}")

    return ConversationHandler.END

async def vente_annuler(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "❌ Vente annulée.",
        reply_markup=kb_nouvelle_vente()
    )
    return ConversationHandler.END

# ── Handler bouton "🔴 Nouvelle vente" ────────────────────────
async def nouvelle_vente_callback(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.edit_message_text(
        "🛒 *Nouvelle vente*\n\nChoisis la catégorie :",
        parse_mode="Markdown",
        reply_markup=kb_categories()
    )
    return CHOIX_CATEGORIE

# ── COMMANDES PATRON ──────────────────────────────────────────
async def rapport(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    aujourd_hui = date.today().strftime("%Y-%m-%d")
    hier        = (date.today() - timedelta(days=1)).strftime("%Y-%m-%d")

    r_hier = get_rapport_jour(hier)
    r_auj  = get_rapport_jour(aujourd_hui)

    # ── Rapport J-1 ──
    texte_hier = formater_rapport(r_hier, titre_emoji="📅")

    # ── Bloc comparaison CA si les deux jours ont des ventes ──
    if r_hier["total"] > 0 and r_auj["total"] > 0:
        diff  = r_auj["total"] - r_hier["total"]
        pct   = (diff / r_hier["total"]) * 100
        icone = "📈" if diff >= 0 else "📉"
        signe = "+" if diff >= 0 else "-"
        comparaison = (
            f"\n{'─'*28}\n"
            f"⚡ *ÉVOLUTION J-1 → Aujourd'hui*\n"
            f"{icone} {signe}{fmt(abs(diff))} ({signe}{abs(pct):.1f} %)\n"
            f"{'─'*28}\n\n"
        )
    else:
        comparaison = f"\n{'─'*28}\n\n"

    # ── Rapport du jour ──
    texte_auj = formater_rapport(r_auj, titre_emoji="📊")

    message_complet = texte_hier + comparaison + texte_auj

    # Telegram limite les messages à 4096 caractères — on envoie en 2 si nécessaire
    if len(message_complet) <= 4096:
        await update.message.reply_text(message_complet, parse_mode="Markdown")
    else:
        await update.message.reply_text(texte_hier, parse_mode="Markdown")
        await update.message.reply_text(texte_auj,  parse_mode="Markdown")

async def solde(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    r = get_rapport_jour()
    await update.message.reply_text(
        f"💰 *CA EN TEMPS RÉEL*\n\n"
        f"📅 {r['jour']}  🕐 {datetime.now().strftime('%H:%M')}\n\n"
        f"💵 *{fmt(r['total'])}*\n"
        f"🎫 {r['nb']} vente(s)",
        parse_mode="Markdown"
    )

async def top(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    r = get_rapport_jour()
    if not r["par_produit"]:
        await update.message.reply_text("🏆 Aucune vente aujourd'hui.")
        return
    medals = ["🥇", "🥈", "🥉", "4️⃣", "5️⃣"]
    lignes = "".join(
        f"{medals[i] if i < len(medals) else '▪️'} {n}\n   → {q} vendu(s) | {fmt(t)}\n"
        for i, (n, q, t) in enumerate(r["par_produit"][:5])
    )
    await update.message.reply_text(
        f"🏆 *TOP PRODUITS — {r['jour']}*\n\n{lignes}",
        parse_mode="Markdown"
    )

async def dernieres(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    rows = get_last_ventes(5)
    if not rows:
        await update.message.reply_text("📋 Aucune vente enregistrée.")
        return
    lignes = "".join(
        f"🕐 {h} | {p} ×{q} = {fmt(t)} — {c}\n"
        for h, c, p, q, t, pay in rows
    )
    await update.message.reply_text(
        f"📋 *5 DERNIÈRES VENTES*\n\n{lignes}",
        parse_mode="Markdown"
    )

# ── MAIN ──────────────────────────────────────────────────────
def main():
    init_db()
    app = Application.builder().token(TOKEN).build()

    conv = ConversationHandler(
        entry_points=[
            CommandHandler("vente", vente_start),
            CallbackQueryHandler(nouvelle_vente_callback, pattern="^nouvelle_vente$"),
        ],
        states={
            CHOIX_CATEGORIE: [CallbackQueryHandler(choix_categorie)],
            CHOIX_PRODUIT:   [CallbackQueryHandler(choix_produit)],
            SAISIE_QUANTITE: [MessageHandler(filters.TEXT & ~filters.COMMAND, saisie_quantite)],
            CHOIX_PAIEMENT:  [CallbackQueryHandler(choix_paiement)],
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

    logger.info("DAM CHAWARMA Bot v5 démarré !")
    app.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()

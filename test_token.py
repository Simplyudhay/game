from telegram import Bot
import asyncio

async def check():
    bot = Bot("8069533921:AAEsM-iMA80Qs5rpqzZu7TWpEdjdiry6FW8")
    me = await bot.get_me()
    print("Bot username:", me.username)

asyncio.run(check())

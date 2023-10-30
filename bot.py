import disnake
from disnake.ext import commands
import requests
import mysql.connector
from dotenv import load_dotenv
import os

# Load environment variables from the .env file
load_dotenv()

# Database connection parameters
DB_PARAMS = {
    'host': os.getenv('DB_HOST'),
    'user': os.getenv('DB_USER'),
    'password': os.getenv('DB_PASS'),
    'database': os.getenv('DB_NAME'),
    'port': os.getenv('DB_PORT')
}

# Initialize bot with intents and command prefix
intents = disnake.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="/", intents=intents, test_guilds=[int(os.getenv('GUILD_ID'))])

# Google Books API key
google_books_api_key = os.getenv('GOOGLE_BOOKS_API_KEY')

# Log channel ID variable
log_channel_id = None

# Accessible channels set
accessible_channels = set()


# Function to execute a query and fetch all results
def execute_query(query, params=()):
    connection = mysql.connector.connect(**DB_PARAMS)
    cursor = connection.cursor()
    cursor.execute(query, params)
    results = cursor.fetchall()
    connection.close()
    return results


# Function to execute a query without fetching results
def execute_non_query(query, params=()):
    connection = mysql.connector.connect(**DB_PARAMS)
    cursor = connection.cursor()
    cursor.execute(query, params)
    connection.commit()
    connection.close()


@bot.event
async def on_ready():
    print(f'Logged in as {bot.user}')
    await bot.sync_commands()


@bot.slash_command(description="Fetches book info")
async def book(inter: disnake.ApplicationCommandInteraction, title: str, author: str):
    if inter.channel_id not in accessible_channels:
        await inter.response.send_message("This command is not allowed in this channel.")
        return
    await inter.response.defer()
    query = f'intitle:{title}+inauthor:{author}'
    url = f'https://www.googleapis.com/books/v1/volumes?q={query}&key={google_books_api_key}'
    response = requests.get(url)
    if response.status_code != 200:
        await inter.followup.send('An error occurred while fetching book info.')
        return
    data = response.json()
    if not data['items']:
        await inter.followup.send('No books found.')
        return
    book_info = data['items'][0]['volumeInfo']
    title = book_info.get('title', 'Unknown Title')
    author = ', '.join(book_info.get('authors', ['Unknown Author']))
    publisher = book_info.get('publisher', 'Unknown Publisher')
    isbn = book_info.get('industryIdentifiers', [{'identifier': 'Unknown ISBN'}])[0]['identifier']
    summary = book_info.get('description', 'No summary available.')
    embed = disnake.Embed(
        title=f'{title} by {author}',
        description=f'Publisher: {publisher}\nISBN: {isbn}\n\n{summary}'
    )
    image_url = book_info.get('imageLinks', {}).get('thumbnail', '')
    if image_url:
        embed.set_image(url=image_url)
    message = await inter.followup.send(embed=embed)
    await message.add_reaction('✅')


@bot.event
async def on_reaction_add(reaction, user):
    if user.bot or reaction.emoji != '✅':
        return
    message = reaction.message
    embed = message.embeds[0]
    title, author = embed.title.split(' by ')
    execute_non_query(
        "INSERT INTO tbr (user_id, book_title, author) VALUES (%s, %s, %s) ON DUPLICATE KEY UPDATE book_title = "
        "VALUES(book_title), author = VALUES(author)",
        (str(user.id), title, author)
    )


@bot.slash_command(description="Add a book to your TBR list")
async def addtbr(inter: disnake.ApplicationCommandInteraction, title: str, author: str):
    if inter.channel_id not in accessible_channels:
        await inter.response.send_message("This command is not allowed in this channel.")
        return
    user_id = str(inter.user.id)
    execute_non_query(
        "INSERT INTO tbr (user_id, book_title, author) VALUES (%s, %s, %s) ON DUPLICATE KEY UPDATE book_title = "
        "VALUES(book_title), author = VALUES(author)",
        (user_id, title, author)
    )
    await inter.response.send_message(f'Added {title} by {author} to your TBR list.')


@bot.slash_command(description="Remove a book from your TBR list")
async def removetbr(inter: disnake.ApplicationCommandInteraction, title: str, author: str):
    if inter.channel_id not in accessible_channels:
        await inter.response.send_message("This command is not allowed in this channel.")
        return
    user_id = str(inter.user.id)
    execute_non_query(
        "DELETE FROM tbr WHERE user_id = %s AND book_title = %s AND author = %s",
        (user_id, title, author)
    )
    await inter.response.send_message(f'Removed {title} by {author} from your TBR list.')


@bot.slash_command(description="View your TBR list or another user's TBR list")
async def tbr(inter: disnake.ApplicationCommandInteraction, user: disnake.User = None):
    if inter.channel_id not in accessible_channels:
        await inter.response.send_message("This command is not allowed in this channel.")
        return
    user = user or inter.user
    books = execute_query("SELECT book_title, author FROM tbr WHERE user_id = %s", (str(user.id),))
    if not books:
        await inter.response.send_message(f'{user.display_name} has no books on their TBR list.')
        return
    embed = disnake.Embed(title=f"{user.display_name}'s TBR List")
    for book_title, author in books:
        embed.add_field(name=book_title, value=author, inline=False)
    await inter.response.send_message(embed=embed)


@bot.slash_command(description="Set log channel")
async def setlogs(inter: disnake.ApplicationCommandInteraction, channel: disnake.TextChannel):
    global log_channel_id
    log_channel_id = channel.id
    await inter.response.send_message(f'Log channel set to {channel.mention}')


@bot.slash_command(description="Set accessible channels")
async def chat(inter: disnake.ApplicationCommandInteraction, channels: disnake.TextChannel):
    global accessible_channels
    accessible_channels.add(channels.id)
    await inter.response.send_message(f'{channels.mention} added to accessible channels.')


@bot.slash_command(description="List accessible channels")
async def listchat(inter: disnake.ApplicationCommandInteraction):
    channels = ', '.join(f'<#{channel_id}>' for channel_id in accessible_channels)
    await inter.response.send_message(f'Accessible channels: {channels}')


@bot.event
async def on_command_error(inter, error):
    if log_channel_id:
        channel = bot.get_channel(log_channel_id)
        await channel.send(f'Error: {error}')


bot.run(os.getenv('DISCORD_BOT_TOKEN'))

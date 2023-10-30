import disnake
from disnake.ext import commands
import requests

intents = disnake.Intents.default()
intents.message_content = True

bot = commands.Bot(command_prefix="/", intents=intents, test_guilds=[1166167748179660820])

# Replace with your Google Books API Key
google_books_api_key = 'AIzaSyCQNto1U_Uqpn7f5QeVzXq8bpxoVs_Pwdg'
book_channel_id = None


@bot.event
async def on_ready():
    print(f'Logged in as {bot.user}')
    await bot.sync_commands()  # This line registers your commands with Discord


@bot.slash_command(name='book', description='Fetch book info')
async def book_command(inter: disnake.ApplicationCommandInteraction, title: str, author: str, publisher: str = None,
                       isbn: str = None, edition: str = None):
    global book_channel_id
    if book_channel_id is not None and inter.channel_id != book_channel_id:
        return

    # Acknowledge the command interaction immediately
    await inter.response.defer()

    query = f'intitle:{title}+inauthor:{author}'
    if publisher:
        query += f'+inpublisher:{publisher}'
    if isbn:
        query += f'+isbn:{isbn}'
    if edition:
        query += f'+edition:{edition}'

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
    isbn_list = book_info.get('industryIdentifiers', [])
    isbn_str = ', '.join(
        [f"{isbn['type']}: {isbn['identifier']}" for isbn in isbn_list]) if isbn_list else 'Unknown ISBN'
    description = book_info.get('description', 'No description available.')
    image_url = book_info.get('imageLinks', {}).get('thumbnail', '')

    embed = disnake.Embed(title=f'{title} by {author}', description=description)
    embed.add_field(name='Publisher', value=publisher, inline=True)
    embed.add_field(name='ISBN', value=isbn_str, inline=True)
    if image_url:
        embed.set_image(url=image_url)
    await inter.followup.send(embed=embed)


@bot.slash_command(name='setchannel', description='Set the channel for book commands')
async def set_channel_command(inter: disnake.ApplicationCommandInteraction, channel: disnake.TextChannel):
    global book_channel_id
    book_channel_id = channel.id
    await inter.response.send_message(f'Channel set to {channel.mention}')


if __name__ == '__main__':
    # Replace with your Discord Bot Token
    bot.run('MTE2ODA1MzM0OTI1NDQ1MTIwMA.GLdexI.bJOEXoyA3M_jMSHtLqLBahtN4Ant8yH8VKnM6Y')

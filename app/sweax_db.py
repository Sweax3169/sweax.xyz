from db_conn import get_db

def create_conversation(user_id, title="Yeni sohbet"):
    with get_db() as conn, conn.cursor() as cur:
        cur.execute("INSERT INTO conversations (user_id, title) VALUES (%s, %s)", (user_id, title))
        return cur.lastrowid  # yeni sohbetin id'si

def get_conversations(user_id):
    with get_db() as conn, conn.cursor() as cur:
        cur.execute("""
            SELECT id, title, updated_at 
            FROM conversations 
            WHERE user_id = %s AND is_archived = 0
            ORDER BY updated_at DESC
        """, (user_id,))
        return cur.fetchall()

def add_message(conversation_id, role, content, token_count=None):
    with get_db() as conn, conn.cursor() as cur:
        cur.execute("""
            INSERT INTO messages (conversation_id, role, content, token_count)
            VALUES (%s, %s, %s, %s)
        """, (conversation_id, role, content, token_count))

def get_messages(conversation_id):
    with get_db() as conn, conn.cursor() as cur:
        cur.execute("""
            SELECT role, content, created_at 
            FROM messages 
            WHERE conversation_id = %s 
            ORDER BY id ASC
        """, (conversation_id,))
        return cur.fetchall()

def rename_conversation(conversation_id, new_title, user_id):
    with get_db() as conn, conn.cursor() as cur:
        cur.execute("""
            UPDATE conversations SET title=%s WHERE id=%s AND user_id=%s
        """, (new_title, conversation_id, user_id))

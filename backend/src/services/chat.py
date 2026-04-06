from tuneapi import tt, ta, tu

import uuid
import time
import asyncio
from asyncio import sleep
from textwrap import dedent
from supabase import Client
from sqlalchemy import select, desc, text, and_
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession

from fastapi import Depends, Query, HTTPException
from fastapi.responses import StreamingResponse

from src import wire as w, db
from src.settings import get_supabase_client, Settings,get_settings
from src.db import get_db_session_fa
from src.dependencies import get_current_user
from src.db import OptimizedQueries
from src.utils.profiler import profile_operation, get_profiler, print_profiler_summary
from src.db import DocumentChunk, SourceDocument


def generate_citation_url(filename: str, spb_client: Client) -> str:
    """Generate a Supabase signed URL for a source file"""
    try:
        # Get supabase URL from client if possible, else use default from settings
        # The supabase client stores url in its _base_url
        base_url = str(spb_client.supabase_url).rstrip('/')
        
        # Create a signed URL for the source file - use 10 years (315360000 seconds) to avoid expiration
        presigned_response = spb_client.storage.from_("source-files").create_signed_url(
            filename, 315360000  # 10 years expiry
        )
        
        if isinstance(presigned_response, dict) and presigned_response.get("error"):
            # Fallback to a generic URL if signing fails
            return f"{base_url}/storage/v1/object/public/source-files/{filename}"
        
        # In some versions it returns the URL directly as a string, in others as a dict
        if isinstance(presigned_response, str):
            return presigned_response
        return presigned_response.get("signedURL", f"{base_url}/storage/v1/object/public/source-files/{filename}")
        
    except Exception as e:
        tu.logger.warning(f"Failed to generate signed URL for {filename}: {e}")
        # Try to get URL from settings for fallback
        try:
            from src.settings import get_settings
            fallback_url = str(get_settings().supabase_url).rstrip('/')
        except:
            fallback_url = "https://jmmqzddkwsmwdczwtrwq.supabase.co"
            
        # Fallback to public URL
        return f"{fallback_url}/storage/v1/object/public/source-files/{filename}"


def refresh_message_citations(messages: list[w.Message], spb_client: Client) -> list[w.Message]:
    """Refresh citation URLs for a list of messages to ensure they haven't expired"""
    for msg in messages:
        if msg.citations:
            for citation in msg.citations:
                # Regenerate the signed URL using the filename
                citation.url = generate_citation_url(citation.name, spb_client)
    return messages


# Mock data and functions for testing
async def _mock_llm_chat(
    session: AsyncSession,
    model: tt.ModelInterface,
    master_thread: tt.Thread,
    conversation: db.Conversation,
    spb_client: Client,
):
    """Mock version of _llm_chat that simulates LLM responses without actual API calls"""

    # Mock response text
    mock_response = "Thank you for your question about spiritual practice. Based on the teachings I've reviewed, I can share some insights about mindfulness and contemplation. The path of spiritual growth involves both inner reflection and outward compassion. Would you like to explore this topic further?"

    # Simulate processing time
    st_ns = tu.SimplerTimes.get_now_fp64()

    # Yield chunks to simulate streaming
    words = mock_response.split()
    for i, word in enumerate(words):
        if i == 0:
            yield ta.to_openai_chunk(tt.assistant(word))
        else:
            yield ta.to_openai_chunk(tt.assistant(" " + word))
        await sleep(0.05)

    # Create mock AI message
    ai_message = db.Message(
        conversation_id=conversation.id,
        role=db.MessageRole.ASSISTANT,
        content=mock_response,
        input_tokens=150,  # Mock values
        output_tokens=75,
        processing_time_ms=int((tu.SimplerTimes.get_now_fp64() - st_ns) * 1000),
        model_used="gpt-5.1-chat-latest",
    )
    session.add(ai_message)
    await session.commit()
    await session.refresh(ai_message)
    yield ta.to_openai_chunk(tt.assistant(f"<message_id>{ai_message.id}</message_id>"))

    # Mock citations - CONVERT TO JSONB
    mock_citations = [
        w.CitationInfo(
            name="spiritual_teachings.pdf",
            url=generate_citation_url("spiritual_teachings.pdf", spb_client),
        ),
        w.CitationInfo(
            name="meditation_guide.pdf",
            url=generate_citation_url("meditation_guide.pdf", spb_client),
        ),
    ]

    # Convert Pydantic models to dict for JSONB storage
    citations_dict = [citation.model_dump() for citation in mock_citations]
    ai_message.citations = citations_dict
    await session.commit()
    await session.refresh(ai_message)

    yield ta.to_openai_chunk(tt.assistant(f"<citations>"))
    for c in mock_citations:
        yield ta.to_openai_chunk(tt.assistant(tu.to_json(c.model_dump(), tight=True)))
    yield ta.to_openai_chunk(tt.assistant("</citations>"))

    # Mock follow up questions - CONVERT TO JSONB
    mock_follow_up = w.FollowUpQuestions(
        questions=[
            "How can I develop a daily mindfulness practice?",
            "What are the key principles of spiritual contemplation?",
            "How do I balance inner reflection with daily responsibilities?",
        ]
    )

    # Convert Pydantic model to dict for JSONB storage
    follow_up_dict = mock_follow_up.model_dump()
    ai_message.follow_up_questions = follow_up_dict
    await session.commit()
    await session.refresh(ai_message)

    yield ta.to_openai_chunk(tt.assistant("<questions>"))
    for q in mock_follow_up.questions:
        yield ta.to_openai_chunk(tt.assistant(q))
    yield ta.to_openai_chunk(tt.assistant("</questions>"))

    # Mock title generation if conversation has no title
    if not conversation.title:
        conversation.title = "Spiritual Guidance Session"
        await session.commit()
        yield ta.to_openai_chunk(tt.assistant(f"<title>{conversation.title}</title>"))


async def _mock_embedding_search(
    session: AsyncSession,
    model: tt.ModelInterface,
    query: str,
) -> list[tuple[str, str]]:
    """Mock embedding search for testing"""
    return [
        ("This is a mock chunk about spiritual teachings.", "spiritual_teachings.pdf"),
        ("Another mock chunk about meditation practices.", "meditation_guide.pdf"),
    ]


async def create_mock_database_entries(
    session: AsyncSession,
) -> tuple[db.UserProfile, db.Conversation]:
    """Create mock database entries for testing"""

    # Create mock user
    user = db.UserProfile(
        phone_number="+1234567890",
        name="Test User",
        role=db.UserRole.USER,
    )
    session.add(user)
    await session.commit()
    await session.refresh(user)

    # Create mock conversation
    conversation = db.Conversation(
        user_id=user.id,
        title="Test Conversation",
    )
    session.add(conversation)
    await session.commit()
    await session.refresh(conversation)
    
    return user, conversation


async def _llm_chat(
    session: AsyncSession,
    model: tt.ModelInterface,
    master_thread: tt.Thread,
    conversation: db.Conversation,
    spb_client: Client,
    user_message: str,
):
    """Real LLM chat with streaming response - PROFILED"""
    
    async with profile_operation("embedding_search") as op:
        chunks = await _embedding_search_optimized(session, model, user_message)
        op.finish(chunks_count=len(chunks))
    
    async with profile_operation("thread_preparation") as op:
        # Validate chunks exist - if not, we cannot answer
        if not chunks or len(chunks) == 0:
            tu.logger.warning(f"No chunks found for query: {user_message}")
            # Return a message indicating no relevant information found
            error_response = "I don't have enough information in my knowledge base to answer this question. Please try rephrasing your question or ask about a different topic."
            yield ta.to_openai_chunk(tt.assistant(error_response))
            yield "[DONE]\n\n"
            return
        
        # Add chunks to thread
        chunk_text = "Here are the ONLY sources of information you can use to answer the question. You MUST ONLY use information from these chunks:\n\n"
        for c_content, c_fname in chunks:
            chunk_text += f"<filename> {c_fname} </filename>\n"
            chunk_text += f"<content> {c_content} </content>\n"
            chunk_text += f"--------------------------------\n"
        
        master_thread.append(tt.human("Find similar chunks from the database"))
        master_thread.append(tt.assistant(chunk_text))
        master_thread.append(
            tt.human(
                dedent(
                    f"""
                    CRITICAL INSTRUCTIONS:
                    - You MUST ONLY use information from the chunks provided above
                    - You MUST NOT use any general knowledge, training data, or information from outside these chunks
                    - If the chunks do not contain enough information to fully answer the question, you must say so explicitly
                    - NEVER make up information or use knowledge from your training data
                    - Base your response ONLY on the content in the chunks above
                    
                    You are given a conversation till now and relevant chunks from the database.
                    Your task is to generate a response to the user's message using ONLY the information from the chunks provided.
                    You will respond in a first person narrative conversational way as if you have understood the idea
                    and are now sharing your thoughts. You will never bring up chunks to the user.
                    
                    User's message: {user_message}
                    
                    Generate a thoughtful response using ONLY the information from the chunks above.
                    """
                )
            )
        )
        op.finish(thread_messages=len(master_thread))
    
    # Start timing for LLM response
    st_ns = tu.SimplerTimes.get_now_fp64()  # Add this line
    
    async with profile_operation("llm_response") as op:
        response = await model.chat_async(master_thread)
        response_content = response.content if hasattr(response, 'content') else str(response)
        op.finish(response_length=len(response_content))
    
    # Yield the response content
    yield ta.to_openai_chunk(tt.assistant(response_content))
    
    async with profile_operation("database_operations") as op:
        # Create AI message
        ai_message = db.Message(
            conversation_id=conversation.id,
            role=db.MessageRole.ASSISTANT,
            content=response_content,
            input_tokens=150,
            output_tokens=75,
            processing_time_ms=int((tu.SimplerTimes.get_now_fp64() - st_ns) * 1000),
            model_used="gpt-4o",
        )
        session.add(ai_message)
        await session.commit()
        await session.refresh(ai_message)
        
        # Add citations - USE ORIGINAL PYDANTIC MODELS
        citations = [
            w.CitationInfo(name=filename, url=generate_citation_url(filename, spb_client))
            for _, filename in chunks[:3]
        ]
        ai_message.citations = citations  # Direct assignment
        
        # Generate follow-up questions - USE ORIGINAL PYDANTIC MODELS
        follow_up = w.FollowUpQuestions(
            questions=[
                "How can I apply this wisdom in my daily life?",
                "What are the deeper spiritual implications?",
                "How can I deepen my understanding of this teaching?",
            ]
        )
        ai_message.follow_up_questions = follow_up  # Direct assignment
        
        # Generate title if conversation doesn't have one
        # Generate title if conversation doesn't have one
        if not conversation.title:
            try:
                # Generate a relevant title
                title_thread = tt.Thread(
                    tt.system("Generate a short, concise title (3-6 words) for this conversation based ONLY on the user's message. Use only the information provided, no general knowledge."),
                    tt.human(f"Message: {user_message}\n\nTitle:")
                )
                title_response = await model.chat_async(title_thread)
                generated_title = str(title_response.content).strip().strip('"')
                conversation.title = generated_title
            except Exception as e:
                tu.logger.error(f"Failed to generate title: {e}")
                conversation.title = "New Conversation"
            
            await session.commit()
        
        op.finish(commits_count=4, citations_count=len(citations))
    
    yield ta.to_openai_chunk(tt.assistant(f"<message_id>{ai_message.id}</message_id>"))

    # Yield citations
    yield ta.to_openai_chunk(tt.assistant(f"<citations>"))
    for c in citations:
        citation_json = tu.to_json(c.model_dump(), tight=True)
        yield ta.to_openai_chunk(tt.assistant(citation_json))
    yield ta.to_openai_chunk(tt.assistant("</citations>"))
    
    # Yield questions
    yield ta.to_openai_chunk(tt.assistant("<questions>"))
    for q in follow_up.questions:
        yield ta.to_openai_chunk(tt.assistant(q))
    yield ta.to_openai_chunk(tt.assistant("</questions>"))
    
    if not conversation.title:
        yield ta.to_openai_chunk(tt.assistant(f"<title>{conversation.title}</title>"))
    
    yield "[DONE]\n\n"
    
    # Print profiling summary
    print_profiler_summary()


async def _llm_chat_optimized(
    session: AsyncSession,
    model: tt.ModelInterface,
    master_thread: tt.Thread,
    conversation: db.Conversation,
    spb_client: Client,
    user_message: str,
):
    """Real LLM chat with PARALLEL processing and BATCH database operations
    
    NOTE: This function is NOT currently used. _llm_chat_streaming_optimized is used instead.
    This function has been fixed to properly add chunks before LLM call.
    """
    
    # Get chunks from database FIRST (critical - chunks must be added before LLM call)
    async with profile_operation("embedding_search") as op:
        chunks = await _embedding_search_optimized(session, model, user_message)
        op.finish(chunks_count=len(chunks))
    
    # Validate chunks exist
    if not chunks or len(chunks) == 0:
        tu.logger.warning(f"No chunks found for query: {user_message}")
        error_response = "I don't have enough information in my knowledge base to answer this question. Please try rephrasing your question or ask about a different topic."
        yield ta.to_openai_chunk(tt.assistant(error_response))
        yield "[DONE]\n\n"
        return
    
    # Add chunks to thread BEFORE calling LLM
    async with profile_operation("thread_preparation") as op:
        chunk_text = "Here are the ONLY sources of information you can use to answer the question. You MUST ONLY use information from these chunks:\n\n"
        for c_content, c_fname in chunks:
            chunk_text += f"<filename> {c_fname} </filename>\n"
            chunk_text += f"<content> {c_content} </content>\n"
            chunk_text += f"--------------------------------\n"
        
        master_thread.append(tt.human("Find similar chunks from the database"))
        master_thread.append(tt.assistant(chunk_text))
        master_thread.append(
            tt.human(
                dedent(
                    f"""
                    CRITICAL INSTRUCTIONS:
                    - You MUST ONLY use information from the chunks provided above
                    - You MUST NOT use any general knowledge, training data, or information from outside these chunks
                    - If the chunks do not contain enough information to fully answer the question, you must say so explicitly
                    - NEVER make up information or use knowledge from your training data
                    - Base your response ONLY on the content in the chunks above
                    
                    You are given a conversation till now and relevant chunks from the database.
                    Your task is to generate a response to the user's message using ONLY the information from the chunks provided.
                    You will respond in a first person narrative conversational way as if you have understood the idea
                    and are now sharing your thoughts. You will never bring up chunks to the user.
                    
                    User's message: {user_message}
                    
                    Generate a thoughtful response using ONLY the information from the chunks above.
                    """
                )
            )
        )
        op.finish(thread_messages=len(master_thread))
    
    # NOW call LLM with chunks in context
    async with profile_operation("llm_response") as op:
        response = await model.chat_async(master_thread)
        response_content = response.content if hasattr(response, 'content') else str(response)
        op.finish(response_length=len(response_content))
    
    # Yield the response content
    yield ta.to_openai_chunk(tt.assistant(response_content))
    
    # BATCH database operations - single commit
    async with profile_operation("batch_database_operations") as op:
        # Create AI message
        ai_message = db.Message(
            conversation_id=conversation.id,
            role=db.MessageRole.ASSISTANT,
            content=response_content,
            input_tokens=150,
            output_tokens=75,
            processing_time_ms=0,  # Will calculate separately
            model_used="mock-gpt-4o",
        )
        
        # Add citations - REMOVE JSONB CONVERSION
        citations = [
            w.CitationInfo(
                name=filename, 
                url=generate_citation_url(filename, spb_client)
            )
            for _, filename in chunks[:3]
        ]
        ai_message.citations = citations

        # Add follow-up questions - REMOVE JSONB CONVERSION
        follow_up = w.FollowUpQuestions(
            questions=[
                "What specific aspects of this topic would you like to explore further?",
                "How does this relate to your personal experience?",
                "What questions do you have about this?"
            ]
        )
        # Remove these lines:
        # follow_up_dict = follow_up.model_dump()
        # ai_message.follow_up_questions = follow_up_dict
        # Use this instead:
        ai_message.follow_up_questions = follow_up
        
        # Generate title if conversation doesn't have one
        # Generate title if conversation doesn't have one
        if not conversation.title:
            try:
                # Generate a relevant title
                title_thread = tt.Thread(
                    tt.system("Generate a short, concise title (3-6 words) for this conversation based ONLY on the user's message. Use only the information provided, no general knowledge."),
                    tt.human(f"Message: {user_message}\n\nTitle:")
                )
                title_response = await model.chat_async(title_thread)
                generated_title = str(title_response.content).strip().strip('"')
                conversation.title = generated_title
            except Exception as e:
                tu.logger.error(f"Failed to generate title: {e}")
                conversation.title = "New Conversation"
        
        # SINGLE BATCH COMMIT
        session.add(ai_message)
        await session.commit()
        await session.refresh(ai_message)
        
        op.finish(commits_count=1, citations_count=len(citations))
    
    yield ta.to_openai_chunk(tt.assistant(f"<message_id>{ai_message.id}</message_id>"))
    
    # Yield citations
    yield ta.to_openai_chunk(tt.assistant(f"<citations>"))
    for c in citations:
        yield ta.to_openai_chunk(tt.assistant(tu.to_json(c.model_dump(), tight=True)))
    yield ta.to_openai_chunk(tt.assistant("</citations>"))

    # Yield questions
    yield ta.to_openai_chunk(tt.assistant("<questions>"))
    for q in follow_up.questions:
        yield ta.to_openai_chunk(tt.assistant(q))
    yield ta.to_openai_chunk(tt.assistant("</questions>"))
    
    if not conversation.title:
        yield ta.to_openai_chunk(tt.assistant(f"<title>{conversation.title}</title>"))
    
    yield "[DONE]\n\n"
    
    print_profiler_summary()


async def _llm_chat_streaming_optimized(
    session: AsyncSession,
    model: tt.ModelInterface,
    master_thread: tt.Thread,
    conversation: db.Conversation,
    spb_client: Client,
    user_message: str,
):
    """Real LLM chat with TRUE STREAMING and parallel processing"""
    
    # Get chunks from database FIRST (this is critical - chunks must be added to thread before LLM call)
    async with profile_operation("embedding_search") as op:
        chunks = await _embedding_search_optimized(session, model, user_message)
        op.finish(chunks_count=len(chunks))
    
    # Add chunks to thread BEFORE calling LLM
    async with profile_operation("thread_preparation") as op:
        # Check if chunks were found
        if not chunks or len(chunks) == 0:
            tu.logger.warning(f"No chunks found for query: {user_message}")
            # Instead of returning early, add context for the LLM to handle gracefully
            master_thread.append(
                tt.human(
                    dedent(
                        f"""
                        CONTEXT: No relevant documents were found in the knowledge base for this query.
                        
                        INSTRUCTIONS:
                        - If this is a greeting (hi, hello, hey, etc.), respond naturally and warmly
                        - If this is a question about who you are or what you do, explain that you're an AI assistant with access to spiritual and meditation teachings
                        - If this is a factual question, politely explain that you don't have information about that topic in your knowledge base
                        - Be honest and helpful
                        
                        User's message: {user_message}
                        
                        Generate an appropriate response.
                        """
                    )
                )
            )
        else:
            # Chunks found - use strict RAG approach
            chunk_text = "Here are the ONLY sources of information you can use to answer the question. You MUST ONLY use information from these chunks:\n\n"
            for c_content, c_fname in chunks:
                chunk_text += f"<filename> {c_fname} </filename>\n"
                chunk_text += f"<content> {c_content} </content>\n"
                chunk_text += f"--------------------------------\n"
            
            master_thread.append(tt.human("Find similar chunks from the database"))
            master_thread.append(tt.assistant(chunk_text))
            master_thread.append(
                tt.human(
                    dedent(
                        f"""
                        CRITICAL INSTRUCTIONS:
                        - You MUST ONLY use information from the chunks provided above
                        - You MUST NOT use any general knowledge, training data, or information from outside these chunks
                        - If the chunks do not contain enough information to fully answer the question, you must say so explicitly
                        - NEVER make up information or use knowledge from your training data
                        - Base your response ONLY on the content in the chunks above
                        
                        You are given a conversation till now and relevant chunks from the database.
                        Your task is to generate a response to the user's message using ONLY the information from the chunks provided.
                        You will respond in a first person narrative conversational way as if you have understood the idea
                        and are now sharing your thoughts. You will never bring up chunks to the user.
                        
                        User's message: {user_message}
                        
                        Generate a thoughtful response using ONLY the information from the chunks above.
                        """
                    )
                )
            )
        op.finish(thread_messages=len(master_thread))

    
    # NOW start streaming LLM response with chunks in context
    async with profile_operation("streaming_llm_response") as op:
        response_content = ""
        
        # Try different streaming approaches
        try:
            # Method 1: Try if model supports streaming directly
            if hasattr(model, 'chat_stream'):
                async for chunk in model.chat_stream(master_thread):
                    content = chunk.content if hasattr(chunk, 'content') else str(chunk)
                    response_content += content
                    yield ta.to_openai_chunk(tt.assistant(content))
            else:
                # Method 2: Use the regular chat method and simulate streaming
                response = await model.chat_async(master_thread)
                response_content = response.content if hasattr(response, 'content') else str(response)
                
                # Stream the response word by word
                words = response_content.split()
                for i, word in enumerate(words):
                    if i == 0:
                        yield ta.to_openai_chunk(tt.assistant(word))
                    else:
                        yield ta.to_openai_chunk(tt.assistant(" " + word))
                    await asyncio.sleep(0.03)  # Faster streaming
        
        except Exception as e:
            # Fallback: Get full response and stream it
            response = await model.chat_async(master_thread)
            response_content = response.content if hasattr(response, 'content') else str(response)
            
            # Stream word by word
            words = response_content.split()
            for i, word in enumerate(words):
                if i == 0:
                    yield ta.to_openai_chunk(tt.assistant(word))
                else:
                    yield ta.to_openai_chunk(tt.assistant(" " + word))
                await asyncio.sleep(0.02)
        
        op.finish(response_length=len(response_content))
    
    # BATCH database operations - single commit
    async with profile_operation("batch_database_operations") as op:
        # Create AI message
        ai_message = db.Message(
            conversation_id=conversation.id,
            role=db.MessageRole.ASSISTANT,
            content=response_content,
            input_tokens=150,
            output_tokens=75,
            processing_time_ms=0,
            model_used="gpt-4o",
        )
        
        # Add citations - CONVERT TO JSONB
        citations = [
            w.CitationInfo(
                name=filename, 
                url=generate_citation_url(filename, spb_client)
            )
            for _, filename in chunks[:3]
        ]
        ai_message.citations = citations
        
        # Generate follow-up questions - CONVERT TO JSONB
        follow_up = w.FollowUpQuestions(
            questions=[
                "How can I apply this wisdom in my daily life?",
                "What are the deeper spiritual implications?",
                "How can I deepen my understanding of this teaching?",
            ]
        )
        
        ai_message.follow_up_questions = follow_up
        
        # Generate title if conversation doesn't have one
        if not conversation.title:
            try:
                # Generate a relevant title
                title_thread = tt.Thread(
                    tt.system("Generate a short, concise title (3-6 words) for this conversation based ONLY on the user's message. Use only the information provided, no general knowledge."),
                    tt.human(f"Message: {user_message}\n\nTitle:")
                )
                title_response = await model.chat_async(title_thread)
                tu.logger.info(f"Title response: {title_response}")
                generated_title = str(title_response).strip().strip('"')
                conversation.title = generated_title
            except Exception as e:
                tu.logger.error(f"Failed to generate title: {e}")
                conversation.title = "New Conversation"
        
        # SINGLE BATCH COMMIT
        session.add(ai_message)
        session.add(conversation)
    await session.commit()
    await session.refresh(ai_message)

    op.finish(commits_count=1, citations_count=len(citations))
    
    # Yield metadata after streaming is complete
    yield ta.to_openai_chunk(tt.assistant(f"<message_id>{ai_message.id}</message_id>"))
    
    # Yield citations
    yield ta.to_openai_chunk(tt.assistant(f"<citations>"))
    for c in citations:
        yield ta.to_openai_chunk(tt.assistant(tu.to_json(c.model_dump(), tight=True)))
    yield ta.to_openai_chunk(tt.assistant("</citations>"))
    
    # Yield questions
    yield ta.to_openai_chunk(tt.assistant("<questions>"))
    for q in follow_up.questions:
        yield ta.to_openai_chunk(tt.assistant(q))
    yield ta.to_openai_chunk(tt.assistant("</questions>"))

    if not conversation.title:
        yield ta.to_openai_chunk(tt.assistant(f"<title>{conversation.title}</title>"))
    
    yield "[DONE]\n\n"
    
    print_profiler_summary()


async def _embedding_search_optimized(
    session: AsyncSession,
    model: tt.ModelInterface,
    query: str,
) -> list[tuple[str, str]]:
    """Optimized embedding search - PROFILED"""
    
    async with profile_operation("embedding_generation") as op:
        embedding_response = await model.embedding_async(
            query, model="text-embedding-3-small"
        )
        embedding = embedding_response.embedding[0]
        op.finish(embedding_dimensions=len(embedding))
    
    async with profile_operation("vector_search") as op:
        query = (
            select(db.DocumentChunk.content, db.SourceDocument.filename)
            .join(db.SourceDocument)
            .where(db.SourceDocument.active == True)
            .order_by(db.DocumentChunk.embedding.max_inner_product(embedding))
            .limit(10)
        )
        result = await session.execute(query)
        chunks: list[tuple[str, str]] = result.all()
        op.finish(chunks_found=len(chunks))
    
    return chunks




async def _embedding_search(
    session: AsyncSession,
    model: tt.ModelInterface,
    query: str,
) -> list[tuple[str, str]]:
    """
    Search the embedding database for the most relevant chunks
    """
    embedding_response = await model.embedding_async(
        query, model="text-embedding-3-small"
    )
    embedding = embedding_response.embedding[0]

    # search the database
    query = (
        select(db.DocumentChunk.content, db.SourceDocument.filename)
        .join(db.SourceDocument)
        .where(db.SourceDocument.active == True)
        .order_by(db.DocumentChunk.embedding.max_inner_product(embedding))
        .limit(10)
    )
    result = await session.execute(query)
    chunks: list[tuple[str, str]] = result.all()
    return chunks

async def chat_completions(
    conversation_id: str,
    request: w.ChatCompletionRequest,
    session: AsyncSession = Depends(get_db_session_fa),
    spb_client: Client = Depends(get_supabase_client),
    user: db.UserProfile = Depends(get_current_user),
    settings:Settings=Depends(get_settings)

):
    """POST /api/chat/completions - STREAMING VERSION"""
    # user = {"id": "b6c3f667-7c8d-4c4b-b3fd-0be55e3ce0ad"}  # Example user

    request_id = f"chat_{conversation_id}_{int(time.time())}"

    # Load conversation
    try:
        async with profile_operation("conversation_load", request_id) as op:
            conversation = await OptimizedQueries.get_conversation_with_messages_and_content(
                session, conversation_id, user.id
            )
            if not conversation:
                raise HTTPException(status_code=404, detail="Conversation not found")
    except HTTPException as e:
        # Re-raise HTTPException as-is (don't wrap it)
        raise
    except Exception as e:
        print("Error loading conversation:", e)
        raise HTTPException(status_code=500, detail=f"Error loading conversation: {e}")

    # Save user message
    try:
        async with profile_operation("user_message_save") as op:
            user_message = db.Message(
                conversation_id=conversation_id,
                role=db.MessageRole.USER,
                content=request.message,
            )
            session.add(user_message)
            await session.commit()
            await session.refresh(user_message)
            op.finish()
    except Exception as e:
        await session.rollback()
        print("Error saving user message:", e)
        raise HTTPException(status_code=500, detail=f"Error saving user message: {e}")

    # Create thread and load all messages
    try:
        async with profile_operation("thread_creation") as op:
            # CRITICAL: System message enforces chunk-only usage - NO general knowledge allowed
            master_thread = tt.Thread(
                tt.system(
                    dedent(
                        f"""
                        The current time is {tu.SimplerTimes.get_now_human()}
                        
                        IMPORTANT: You are a knowledge assistant that ONLY uses information from the provided document chunks.
                        You MUST NOT use any general knowledge, training data, or information from outside the provided chunks.
                        If the chunks do not contain enough information to answer a question, you must say so explicitly.
                        NEVER make up information or use knowledge from your training data.
                        """
                    ).strip()
                ),
                id=conversation_id,
            )

            all_messages_query = (
                select(db.Message)
                .where(db.Message.conversation_id == conversation_id)
                .order_by(db.Message.created_at)
            )
            result = await session.execute(all_messages_query)
            all_messages = result.scalars().all()

            for m in all_messages:
                master_thread.append(tt.Message(m.content, m.role.value))

            op.finish(thread_messages=len(master_thread))
    except Exception as e:
        print("Error creating thread or loading messages:", e)
        raise HTTPException(status_code=500, detail=f"Error creating thread: {e}")

    # Mock processing branch
    if request.mock:
        try:
            async with profile_operation("mock_processing") as op:
                model = None
                chunks = await _mock_embedding_search(session, model, request.message)
                op.finish(chunks_count=len(chunks))

            return StreamingResponse(
                _mock_llm_chat(session, model, master_thread, conversation, spb_client),
                media_type="text/plain",
            )
        except Exception as e:
            print("Error in mock processing:", e)
            raise HTTPException(status_code=500, detail=f"Mock processing error: {e}")

    # Real streaming LLM processing branch
    try:
        async with profile_operation("streaming_llm_processing") as op:
            model = ta.Openai(id="gpt-4-turbo", api_token=settings.openai_token)
            response = StreamingResponse(
                _llm_chat_streaming_optimized(session, model, master_thread, conversation, spb_client, request.message),
                media_type="text/plain",
            )
            op.finish()
            return response
    except Exception as e:
        tu.logger.error(f"Error in streaming LLM processing: {e}")
        raise HTTPException(status_code=500, detail=f"Streaming LLM error: {e}")




async def create_conversation(
    user: db.UserProfile = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session_fa),
) -> w.Conversation:
    """POST /api/chat - Create a new conversation"""
    try:
        # print("CREATE CONVERSTATION")
        conversation = db.Conversation(
            user_id=user.id,
            title= None,
        )
        session.add(conversation)
        await session.commit()
        await session.refresh(conversation)
        return await conversation.to_bm()
    
    except Exception as e:
        await session.rollback()
        print("Error creating conversation:", e)
        raise HTTPException(status_code=500, detail=str(e))




async def delete_conversation(
    conversation_id: str,
    session: AsyncSession = Depends(get_db_session_fa),
    user: db.UserProfile = Depends(get_current_user),
    spb_client: Client = Depends(get_supabase_client),
) -> None:
    """DELETE /api/chat/{conversation_id} - Delete a conversation and all associated data"""
    
    # Get the conversation to verify ownership
    query = select(db.Conversation).where(
        and_(
            db.Conversation.id == conversation_id,
            db.Conversation.user_id == user.id,
        )
    )
    result = await session.execute(query)
    conversation = result.scalar_one_or_none()
    
    if not conversation:
        raise HTTPException(status_code=404, detail="Conversation not found")

    # 1. Find all content generations associated with this conversation to get file paths
    # We load them before deleting the conversation to ensure we have the paths
    content_query = select(db.ContentGeneration).where(
        db.ContentGeneration.conversation_id == conversation.id
    )
    content_result = await session.execute(content_query)
    content_generations = content_result.scalars().all()

    # 2. Delete actual files from Supabase storage
    if content_generations:
        paths_to_delete = [
            cg.content_path for cg in content_generations if cg.content_path
        ]
        if paths_to_delete:
            try:
                # Remove files from the "generations" bucket
                spb_client.storage.from_("generations").remove(paths_to_delete)
                tu.logger.info(f"Deleted {len(paths_to_delete)} files from storage for conversation {conversation_id}")
            except Exception as e:
                tu.logger.warning(f"Failed to delete files from storage for conversation {conversation_id}: {e}")

    # 3. Hard delete the conversation from the database
    # cascade="all, delete-orphan" in DB models handles associated messages and content generation records
    await session.delete(conversation)
    await session.commit()
    
    tu.logger.info(f"Successfully hard deleted conversation {conversation_id} and all associated data")



async def mark_conversation_as_deleted(
    conversation_id: str,
    session: AsyncSession = Depends(get_db_session_fa),
    user: db.UserProfile = Depends(get_current_user),
) -> None:
    """POST /api/chat/{conversation_id}/mark-as-deleted - Mark a conversation as deleted"""
    
    # Get the conversation to verify ownership
    query = select(db.Conversation).where(
        and_(
            db.Conversation.id == conversation_id,
            db.Conversation.user_id == user.id,
        )
    )
    result = await session.execute(query)
    conversation = result.scalar_one_or_none()
    
    if not conversation:
        raise HTTPException(status_code=404, detail="Conversation not found")

    conversation.mark_as_deleted = True

    if not conversation.deleted_at:
        conversation.deleted_at = tu.SimplerTimes.get_now_datetime()
        
    await session.commit()


async def update_conversation_title(
    conversation_id: str,
    request: w.UpdateConversationTitleRequest,
    session: AsyncSession = Depends(get_db_session_fa),
    user: db.UserProfile = Depends(get_current_user),
) -> w.Conversation:
    """PUT /api/chat/{conversation_id}/title - Update conversation title"""
    
    # Get the conversation to verify ownership
    query = select(db.Conversation).where(
        and_(
        db.Conversation.id == conversation_id,
        db.Conversation.user_id == user.id,
        )
    )
    result = await session.execute(query)
    conversation = result.scalar_one_or_none()
    
    if not conversation:
        raise HTTPException(status_code=404, detail="Conversation not found")

    # Update the title
    conversation.title = request.title
    await session.commit()
    await session.refresh(conversation)
    
    return await conversation.to_bm()


async def submit_conversation_feedback(
    conversation_id: str,
    request: w.MessageFeedbackRequest,
    session: AsyncSession = Depends(get_db_session_fa),
    user: db.UserProfile = Depends(get_current_user),
) -> None:
    """POST /api/chat/{conversation_id}/feedback - Submit feedback for a message"""
    
    # Get the message to verify it belongs to the conversation
    query = select(db.Message).join(db.Conversation).where(
        and_(
            db.Message.id == request.message_id,
        db.Conversation.id == conversation_id,
        db.Conversation.user_id == user.id,
    )
    )
    result = await session.execute(query)
    message = result.scalar_one_or_none()
    
    if not message:
        raise HTTPException(status_code=404, detail="Message not found")

    # Update the message with feedback
    message.feedback_type = db.FeedbackType(request.type)
    message.feedback_comment = request.comment
    message.feedback_given_at = tu.SimplerTimes.get_now_datetime()
    await session.commit()


async def get_conversation(
    conversation_id: str,
    session: AsyncSession = Depends(get_db_session_fa),
    user: db.UserProfile = Depends(get_current_user),
    spb_client: Client = Depends(get_supabase_client),
) -> w.ConversationDetailResponse:
    """GET /api/chat/{conversation_id} - Get a specific conversation with messages"""
   
    
    # # Use optimized query to get conversation with messages and content
    # conversation = await OptimizedQueries.get_conversation_with_messages_and_content(
    #     session, conversation_id, user.id
    # )

     # Use optimized query to get conversation with messages and content
    conversation = await OptimizedQueries.get_conversation_with_messages_and_content(
        session, conversation_id, user.id
    )
    
    if not conversation:
        raise HTTPException(status_code=404, detail="Conversation not found")
    
    # Convert to wire format
    conversation_bm = await conversation.to_bm()
    
    # Convert messages to wire format
    messages_bm = [await msg.to_bm() for msg in conversation.messages]
    
    # Refresh citation URLs to ensure they haven't expired
    messages_bm = refresh_message_citations(messages_bm, spb_client)
    
    # Convert content generations to wire format (if any)
    content_generations_bm = None
    if conversation.content_generations:
        content_generations_bm = [await cg.to_bm() for cg in conversation.content_generations]
    
    return w.ConversationDetailResponse(
        conversation=conversation_bm,
        messages=messages_bm,
        content_generations=content_generations_bm
    )


async def get_conversations(
    limit: int = Query(10, le=50),
    offset: int = Query(0),
    session: AsyncSession = Depends(get_db_session_fa),
    user: db.UserProfile = Depends(get_current_user),
) -> w.ConversationsListResponse:
    """GET /api/chat - Get user's conversations"""
    
    query = (
        select(db.Conversation)
        .where(db.Conversation.user_id == user.id)
        .order_by(db.Conversation.updated_at.desc())
        .limit(limit)
        .offset(offset)
    )
    
    result = await session.execute(query)
    conversations = result.scalars().all()
    
    return w.ConversationsListResponse(
        conversations=[await conv.to_bm() for conv in conversations]
    )

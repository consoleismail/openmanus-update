"""Main trigger engine that coordinates rules and ML-based triggers."""

import asyncio
from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field

from app.context.models import UserContext
from app.triggers.models import Trigger, TriggerResult, TriggerQueue, Priority
from app.triggers.rules import RulesEngine, Rule
from app.logger import logger


class TriggerEngineConfig(BaseModel):
    """Configuration for the trigger engine."""
    
    enable_rules: bool = True
    enable_ml_prediction: bool = False
    evaluation_interval: int = 60  # seconds
    max_concurrent_triggers: int = 5


class TriggerEngine:
    """
    Main trigger engine that evaluates conditions and fires triggers.
    
    Coordinates between:
    - Rules-based triggers (deterministic)
    - ML-predicted triggers (probabilistic, when enabled)
    
    Manages a priority queue of pending triggers and 
    provides them to the workflow executor.
    """
    
    def __init__(self, config: Optional[TriggerEngineConfig] = None):
        """
        Initialize the trigger engine.
        
        Args:
            config: Engine configuration
        """
        self.config = config or TriggerEngineConfig()
        self.rules_engine = RulesEngine()
        self.queue = TriggerQueue()
        self._running = False
        self._evaluation_task: Optional[asyncio.Task] = None
        self._listeners: List[callable] = []
    
    def add_rule(self, rule: Rule) -> None:
        """Add a rule to the engine."""
        self.rules_engine.add_rule(rule)
    
    def remove_rule(self, rule_id: str) -> None:
        """Remove a rule from the engine."""
        self.rules_engine.remove_rule(rule_id)
    
    async def evaluate(self, context: UserContext) -> List[TriggerResult]:
        """
        Evaluate all triggers against the current context.
        
        Args:
            context: Current user context
            
        Returns:
            List of TriggerResults for triggers that fired
        """
        results = []
        
        # Evaluate rules-based triggers
        if self.config.enable_rules:
            rule_results = self.rules_engine.evaluate(context)
            results.extend(rule_results)
        
        # Evaluate ML-based triggers (when implemented)
        if self.config.enable_ml_prediction:
            ml_results = await self._evaluate_ml_triggers(context)
            results.extend(ml_results)
        
        # Add fired triggers to the queue
        for result in results:
            if result.fired:
                self.queue.add(result)
                await self._notify_listeners(result)
        
        return results
    
    async def _evaluate_ml_triggers(self, context: UserContext) -> List[TriggerResult]:
        """
        Evaluate ML-based triggers.
        
        This is a placeholder for future ML-based trigger prediction.
        When implemented, this would use a trained model to predict
        which actions the user might want based on context patterns.
        """
        # TODO: Implement ML-based trigger prediction
        # This would involve:
        # 1. Encoding the context into features
        # 2. Running inference on a prediction model
        # 3. Converting predictions to TriggerResults
        return []
    
    def get_pending_triggers(self, max_count: int = 10) -> List[TriggerResult]:
        """
        Get pending triggers from the queue.
        
        Args:
            max_count: Maximum number of triggers to return
            
        Returns:
            List of pending TriggerResults
        """
        results = []
        while len(results) < max_count and self.queue:
            result = self.queue.pop()
            if result:
                results.append(result)
        return results
    
    def peek_next_trigger(self) -> Optional[TriggerResult]:
        """Peek at the next trigger without removing it."""
        return self.queue.peek()
    
    @property
    def pending_count(self) -> int:
        """Number of pending triggers in the queue."""
        return len(self.queue)
    
    async def start_evaluation_loop(
        self,
        context_provider: callable,
        interval: Optional[int] = None
    ) -> None:
        """
        Start the continuous evaluation loop.
        
        Args:
            context_provider: Async callable that returns UserContext
            interval: Evaluation interval in seconds (uses config default if not specified)
        """
        if self._running:
            logger.warning("Trigger evaluation loop already running")
            return
        
        self._running = True
        interval = interval or self.config.evaluation_interval
        
        logger.info(f"Starting trigger evaluation loop (interval: {interval}s)")
        
        while self._running:
            try:
                # Get current context
                context = await context_provider()
                
                # Evaluate triggers
                results = await self.evaluate(context)
                
                if results:
                    logger.info(f"Trigger evaluation: {len(results)} triggers fired")
                
            except Exception as e:
                logger.error(f"Error in trigger evaluation loop: {e}")
            
            await asyncio.sleep(interval)
    
    def stop_evaluation_loop(self) -> None:
        """Stop the continuous evaluation loop."""
        self._running = False
        if self._evaluation_task:
            self._evaluation_task.cancel()
            self._evaluation_task = None
        logger.info("Trigger evaluation loop stopped")
    
    def add_listener(self, callback: callable) -> None:
        """Add a listener for trigger events."""
        self._listeners.append(callback)
    
    def remove_listener(self, callback: callable) -> None:
        """Remove a trigger event listener."""
        if callback in self._listeners:
            self._listeners.remove(callback)
    
    async def _notify_listeners(self, result: TriggerResult) -> None:
        """Notify all listeners of a trigger event."""
        for listener in self._listeners:
            try:
                if asyncio.iscoroutinefunction(listener):
                    await listener(result)
                else:
                    listener(result)
            except Exception as e:
                logger.error(f"Error notifying trigger listener: {e}")
    
    def clear_queue(self) -> None:
        """Clear all pending triggers."""
        self.queue.clear()
    
    def get_statistics(self) -> dict:
        """Get engine statistics."""
        return {
            "rules_count": len(self.rules_engine.rules),
            "pending_triggers": len(self.queue),
            "evaluation_running": self._running,
            "ml_enabled": self.config.enable_ml_prediction,
        }
